from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "rootloom"
    / "skills"
    / "setup-rootloom"
    / "scripts"
    / "setup_rootloom.py"
)
SPEC = importlib.util.spec_from_file_location("setup_rootloom", SCRIPT)
assert SPEC and SPEC.loader
setup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = setup
SPEC.loader.exec_module(setup)


class SetupRootloomTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="rootloom-setup-", dir=Path.home())
        self.addCleanup(self.temporary.cleanup)
        self.codex_home = Path(self.temporary.name) / "codex-home"
        self.codex_home.mkdir()

    def test_personal_is_default_and_contains_only_personal_components(self) -> None:
        result = setup.apply_plan(self.codex_home, replace_conflicts=False)
        self.assertEqual(result["capabilities"], list(setup.PRESETS["personal"]))
        self.assertTrue((self.codex_home / "AGENTS.md").is_file())
        self.assertTrue((self.codex_home / "rules" / "rootloom.rules").is_file())
        self.assertFalse((self.codex_home / "agents").exists())
        self.assertFalse((self.codex_home / "high-assurance.config.toml").exists())
        policy = json.loads(
            (self.codex_home / setup.COMPONENT_POLICY_PATH).read_text(encoding="utf-8")
        )
        self.assertEqual(policy["hooks"], {"project-guidance-hook": True})

    def test_autonomy_always_includes_its_global_authorization_policy(self) -> None:
        selected = setup.normalize_capabilities(["autonomy"])
        self.assertEqual(selected, ("global-policy", "autonomy"))
        self.assertEqual(
            setup.components_for_capabilities(selected),
            ("global-guidance", "command-rules"),
        )

    def test_legacy_capability_and_preset_aliases_are_hidden_but_supported(self) -> None:
        self.assertEqual(
            setup.normalize_capabilities(["command-safety"]),
            ("global-policy", "autonomy"),
        )
        self.assertEqual(setup.normalize_preset("engineering"), "personal")
        catalog = setup.catalog_payload()
        self.assertNotIn("engineering", catalog["presets"])
        self.assertNotIn("command-safety", catalog["capabilities"])
        self.assertEqual(
            catalog["compatibility_aliases"]["presets"],
            {"engineering": "personal"},
        )

    def test_plan_apply_status_and_rollback_round_trip(self) -> None:
        version, _targets, actions, _desired = setup.build_plan(self.codex_home)
        self.assertTrue(version)
        self.assertTrue(all(item.action == "create" for item in actions))

        applied = setup.apply_plan(self.codex_home, replace_conflicts=False)
        self.assertEqual(applied["status"], "applied")
        status = setup.status_payload(self.codex_home)
        self.assertEqual(status["status"], "installed")
        self.assertTrue(all(item["action"] == "unchanged" for item in status["actions"]))

        rolled_back = setup.rollback(self.codex_home)
        self.assertEqual(rolled_back["status"], "rolled_back")
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        self.assertFalse((self.codex_home / "rules" / "rootloom.rules").exists())
        self.assertFalse((self.codex_home / setup.COMPONENT_POLICY_PATH).exists())

    def test_install_merges_user_owned_agents_and_rollback_restores_mode(self) -> None:
        agents = self.codex_home / "AGENTS.md"
        agents.write_text("# Mine\n", encoding="utf-8")
        if os.name != "nt":
            agents.chmod(0o644)

        planned = setup.build_plan(self.codex_home)[2]
        agents_action = next(item for item in planned if item.path == "AGENTS.md")
        self.assertEqual(agents_action.action, "update")
        setup.apply_plan(self.codex_home, replace_conflicts=False)
        expected = (
            setup.desired_bytes(setup.all_targets(setup.plugin_root())[0], setup.FULL_CAPABILITIES)
            + b"\n# Mine\n"
        )
        self.assertEqual(agents.read_bytes(), expected)

        setup.rollback(self.codex_home)
        self.assertEqual(agents.read_text(encoding="utf-8"), "# Mine\n")
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(agents.stat().st_mode), 0o644)

    def test_rollback_refuses_post_setup_edits(self) -> None:
        setup.apply_plan(self.codex_home, replace_conflicts=False)
        agents = self.codex_home / "AGENTS.md"
        agents.write_text(agents.read_text(encoding="utf-8") + "\n# edit\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "changed after setup"):
            setup.rollback(self.codex_home)

    def test_capability_change_requires_rollback(self) -> None:
        setup.apply_plan(
            self.codex_home,
            replace_conflicts=False,
            capabilities=setup.PRESETS["guidance"],
        )
        with self.assertRaisesRegex(RuntimeError, "roll back first"):
            setup.apply_plan(
                self.codex_home,
                replace_conflicts=False,
                capabilities=setup.PRESETS["personal"],
            )
        setup.rollback(self.codex_home)
        result = setup.apply_plan(
            self.codex_home,
            replace_conflicts=False,
            capabilities=setup.PRESETS["personal"],
        )
        self.assertEqual(result["status"], "applied")

    def test_update_rollback_restores_previous_install_and_all_unwinds_chain(self) -> None:
        setup.apply_plan(self.codex_home, replace_conflicts=False)
        original = (self.codex_home / "AGENTS.md").read_bytes()
        original_desired = setup.desired_bytes

        def updated(target: object, capabilities: tuple[str, ...]) -> bytes:
            value = original_desired(target, capabilities)
            if isinstance(target, setup.Target) and target.relative_path == "AGENTS.md":
                return value.replace(
                    setup.MANAGED_END,
                    b"# simulated update\n" + setup.MANAGED_END,
                )
            return value

        with mock.patch.object(setup, "desired_bytes", side_effect=updated):
            setup.apply_plan(self.codex_home, replace_conflicts=False)
        self.assertNotEqual((self.codex_home / "AGENTS.md").read_bytes(), original)

        one = setup.rollback(self.codex_home)
        self.assertEqual(one["status"], "rolled_back_to_previous")
        self.assertEqual((self.codex_home / "AGENTS.md").read_bytes(), original)
        self.assertEqual(setup.load_state(self.codex_home)["status"], "installed")

        all_result = setup.rollback_all(self.codex_home)
        self.assertEqual(all_result["status"], "rolled_back_all")
        self.assertFalse((self.codex_home / "AGENTS.md").exists())

    def test_explicit_install_and_upgrade_preserve_selection(self) -> None:
        installed = setup.apply_plan(
            self.codex_home,
            replace_conflicts=False,
            capabilities=setup.PRESETS["guidance"],
            operation="install",
        )
        self.assertEqual(installed["status"], "installed")
        upgraded = setup.apply_plan(
            self.codex_home,
            replace_conflicts=False,
            capabilities=setup.PRESETS["guidance"],
            operation="upgrade",
        )
        self.assertEqual(upgraded["status"], "up_to_date")
        self.assertEqual(upgraded["capabilities"], list(setup.PRESETS["guidance"]))
        with self.assertRaisesRegex(RuntimeError, "already installed"):
            setup.apply_plan(
                self.codex_home,
                replace_conflicts=False,
                capabilities=setup.PRESETS["guidance"],
                operation="install",
            )

    def test_version_only_upgrade_updates_state_without_backup(self) -> None:
        setup.apply_plan(
            self.codex_home, replace_conflicts=False, operation="install"
        )
        state = setup.load_state(self.codex_home)
        state["version"] = "2.0.0"
        setup.atomic_write(
            self.codex_home / setup.STATE_PATH,
            (json.dumps(state, indent=2, sort_keys=True) + "\n").encode(),
        )
        before_backup = state["backup"]
        result = setup.apply_plan(
            self.codex_home, replace_conflicts=False, operation="upgrade"
        )
        self.assertEqual(result["status"], "upgraded")
        self.assertEqual(result["previous_version"], "2.0.0")
        current = setup.load_state(self.codex_home)
        self.assertEqual(current["version"], setup.plugin_version(setup.plugin_root()))
        self.assertEqual(current["backup"], before_backup)

    def test_upgrade_merges_managed_agents_and_preserves_user_content(self) -> None:
        setup.apply_plan(
            self.codex_home, replace_conflicts=False, operation="install"
        )
        agents = self.codex_home / "AGENTS.md"
        original = agents.read_bytes()
        state = setup.load_state(self.codex_home)
        self.assertEqual(
            state["files"]["AGENTS.md"],
            setup.sha256_bytes(original),
        )
        user_content = b"\n## Shared server profiles\n\n- Keep this custom profile.\n"
        agents.write_bytes(original + user_content)
        status = setup.status_payload(self.codex_home)
        self.assertEqual(status["drifted_paths"], [])
        self.assertEqual(
            next(item for item in status["actions"] if item["path"] == "AGENTS.md")[
                "action"
            ],
            "unchanged",
        )

        original_desired = setup.desired_bytes

        def updated(target: object, capabilities: tuple[str, ...]) -> bytes:
            value = original_desired(target, capabilities)
            if isinstance(target, setup.Target) and target.relative_path == "AGENTS.md":
                return value.replace(
                    setup.MANAGED_END,
                    b"# simulated update\n" + setup.MANAGED_END,
                )
            return value

        with mock.patch.object(setup, "desired_bytes", side_effect=updated):
            upgraded = setup.apply_plan(
                self.codex_home, replace_conflicts=False, operation="upgrade"
            )

        merged = agents.read_bytes()
        self.assertEqual(upgraded["status"], "upgraded")
        self.assertIn(b"# simulated update\n", merged)
        self.assertTrue(merged.endswith(user_content))
        setup.rollback(self.codex_home)
        self.assertEqual(agents.read_bytes(), original + user_content)

    def test_upgrade_refuses_managed_block_drift_even_with_replace_flag(self) -> None:
        setup.apply_plan(
            self.codex_home, replace_conflicts=False, operation="install"
        )
        agents = self.codex_home / "AGENTS.md"
        edited = agents.read_text(encoding="utf-8").replace(
            "# Global Codex Working Agreement",
            "# Edited managed agreement",
        )
        agents.write_text(edited, encoding="utf-8")
        status = setup.status_payload(self.codex_home)
        self.assertEqual(status["drifted_paths"], ["AGENTS.md"])
        with self.assertRaisesRegex(RuntimeError, "changed after installation"):
            setup.apply_plan(
                self.codex_home,
                replace_conflicts=True,
                operation="upgrade",
            )
        self.assertEqual(agents.read_text(encoding="utf-8"), edited)

    def test_malformed_agents_markers_are_never_replaced(self) -> None:
        agents = self.codex_home / "AGENTS.md"
        malformed = b"<!-- rootloom:managed-start version=1 -->\n# Mine\n"
        agents.write_bytes(malformed)

        for replace_conflicts in (False, True):
            with self.assertRaisesRegex(RuntimeError, "malformed"):
                setup.apply_plan(
                    self.codex_home,
                    replace_conflicts=replace_conflicts,
                    operation="install",
                )
            self.assertEqual(agents.read_bytes(), malformed)

    def test_upgrade_removes_pristine_retired_target_and_rollback_restores_it(self) -> None:
        setup.apply_plan(
            self.codex_home, replace_conflicts=False, operation="install"
        )
        retired = self.codex_home / "rules" / "retired.rules"
        retired.write_bytes(b"retired managed content\n")
        state = setup.load_state(self.codex_home)
        state["files"]["rules/retired.rules"] = setup.sha256_bytes(
            retired.read_bytes()
        )
        setup.atomic_write(
            self.codex_home / setup.STATE_PATH,
            (json.dumps(state, indent=2, sort_keys=True) + "\n").encode(),
        )

        upgraded = setup.apply_plan(
            self.codex_home, replace_conflicts=False, operation="upgrade"
        )
        self.assertEqual(upgraded["status"], "upgraded")
        self.assertFalse(retired.exists())
        self.assertIn(
            "remove",
            {
                item["action"]
                for item in upgraded["actions"]
                if item["path"] == "rules/retired.rules"
            },
        )

        rolled_back = setup.rollback(self.codex_home)
        self.assertEqual(rolled_back["status"], "rolled_back_to_previous")
        self.assertEqual(retired.read_bytes(), b"retired managed content\n")

    def test_upgrade_rejects_unsafe_managed_state_path(self) -> None:
        setup.apply_plan(
            self.codex_home, replace_conflicts=False, operation="install"
        )
        state = setup.load_state(self.codex_home)
        state["files"]["../outside"] = setup.sha256_bytes(b"outside")
        setup.atomic_write(
            self.codex_home / setup.STATE_PATH,
            (json.dumps(state, indent=2, sort_keys=True) + "\n").encode(),
        )
        with self.assertRaisesRegex(ValueError, "normalized"):
            setup.apply_plan(
                self.codex_home, replace_conflicts=False, operation="upgrade"
            )

    def test_skills_only_disables_hook_without_global_assets(self) -> None:
        result = setup.apply_plan(
            self.codex_home,
            replace_conflicts=False,
            capabilities=setup.PRESETS["skills-only"],
        )
        self.assertEqual(result["capabilities"], [])
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        policy = json.loads(
            (self.codex_home / setup.COMPONENT_POLICY_PATH).read_text(encoding="utf-8")
        )
        self.assertEqual(policy["hooks"], {"project-guidance-hook": False})
        self.assertEqual(setup.status_payload(self.codex_home)["capabilities"], [])

        args = mock.Mock(preset=None, capabilities=None)
        self.assertEqual(setup.selected_capabilities(args, self.codex_home), ())

    def test_explicit_empty_status_selection_does_not_fall_back_to_personal(self) -> None:
        status = setup.status_payload(self.codex_home, ())
        self.assertEqual(status["capabilities"], [])
        self.assertEqual(status["components"], [])
        self.assertEqual(
            [item["path"] for item in status["actions"]],
            [str(setup.COMPONENT_POLICY_PATH)],
        )

    def test_setup_lock_refuses_competing_operation(self) -> None:
        with setup.setup_lock(self.codex_home):
            with self.assertRaisesRegex(RuntimeError, "another Rootloom setup operation"):
                setup.apply_plan(self.codex_home, replace_conflicts=False)

    def test_interrupted_apply_is_completed_from_transaction_journal(self) -> None:
        original_atomic_write = setup.atomic_write

        def interrupt_after_first_target(path: Path, value: bytes, mode: int = 0o600) -> None:
            original_atomic_write(path, value, mode)
            if path == self.codex_home / "AGENTS.md":
                raise RuntimeError("simulated interruption")

        with mock.patch.object(setup, "atomic_write", side_effect=interrupt_after_first_target):
            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                setup.apply_plan(self.codex_home, replace_conflicts=False)

        self.assertTrue((self.codex_home / setup.TRANSACTION_PATH).is_file())
        status = setup.status_payload(self.codex_home)
        self.assertEqual(
            status["pending_transaction"]["paths"][-1],
            setup.STATE_PATH,
        )

        agents = self.codex_home / "AGENTS.md"
        agents.write_text("# changed after interruption\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "pending setup transaction conflicts with AGENTS.md"):
            setup.apply_plan(self.codex_home, replace_conflicts=False)
        self.assertEqual(agents.read_text(encoding="utf-8"), "# changed after interruption\n")

        agents.unlink()

        recovered = setup.apply_plan(self.codex_home, replace_conflicts=False)
        self.assertEqual(recovered["status"], "unchanged")
        self.assertFalse((self.codex_home / setup.TRANSACTION_PATH).exists())
        self.assertEqual(setup.status_payload(self.codex_home)["status"], "installed")

    def test_symlinked_target_is_refused(self) -> None:
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (self.codex_home / "rules").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlinked"):
            setup.apply_plan(self.codex_home, replace_conflicts=True)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
