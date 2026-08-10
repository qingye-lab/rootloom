from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SELECTOR_PATH = ROOT / "scripts" / "impact_tests.py"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ImpactTestSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.selector = load_module("rootloom_impact_tests", SELECTOR_PATH)

    def select(self, *paths: str):
        return self.selector.select_paths(paths)

    def test_documentation_only_change_runs_validation_without_unit_tests(self) -> None:
        selection = self.select("README.md", "docs/maturity.zh-CN.md")

        self.assertEqual(selection.mode, "validate")
        self.assertEqual(selection.modules, ())
        self.assertFalse(selection.portable)
        self.assertFalse(selection.codex)

    def test_change_skill_selects_behavior_and_portable_package_tests(self) -> None:
        selection = self.select(
            "plugins/rootloom/skills/operating-coding-change/SKILL.md"
        )

        self.assertEqual(selection.groups, ("packaging", "change"))
        self.assertEqual(
            selection.modules,
            (
                "tests.test_host_adapters",
                "tests.test_portable_plugin",
                "tests.test_core_reset_eval",
                "tests.test_core_reset_runner",
            ),
        )
        self.assertTrue(selection.portable)
        self.assertFalse(selection.codex)

    def test_global_setup_guidance_selects_setup_and_codex_contracts(self) -> None:
        selection = self.select("plugins/rootloom/assets/system/AGENTS.md")

        self.assertEqual(selection.groups, ("setup", "change"))
        self.assertTrue(selection.portable)
        self.assertTrue(selection.codex)

    def test_change_contract_template_selects_behavior_tests(self) -> None:
        selection = self.select(
            "plugins/rootloom/resources/contracts/DECISION.template.md"
        )

        self.assertEqual(selection.groups, ("change",))

    def test_markdown_outside_documentation_roots_falls_back_to_full(self) -> None:
        selection = self.select("plugins/rootloom/new-runtime-policy.md")

        self.assertEqual(selection.mode, "full")
        self.assertIn("unclassified changed path", selection.reasons[0])

    def test_changed_test_maps_to_its_own_component(self) -> None:
        selection = self.select("tests/test_web_telemetry.py")

        self.assertEqual(selection.groups, ("web",))
        self.assertEqual(selection.modules, ("tests.test_web_telemetry",))

    def test_platform_lane_is_limited_to_platform_sensitive_components(self) -> None:
        for path in (
            "plugins/rootloom/resources/evidence/analyze_change.py",
            "experiments/rootloom-memory/lib/rootloom_memory.py",
        ):
            with self.subTest(path=path):
                self.assertTrue(self.select(path).portable)
        for path in ("site/main.js", "evals/core-reset/evaluate.py"):
            with self.subTest(path=path):
                self.assertFalse(self.select(path).portable)

    def test_shared_test_selection_change_falls_back_to_full(self) -> None:
        for path in (
            "Makefile",
            ".github/workflows/ci.yml",
            "scripts/impact_tests.py",
            "scripts/validate_repo.py",
            "tests/test_impact_tests.py",
        ):
            with self.subTest(path=path):
                selection = self.select(path)
                self.assertEqual(selection.mode, "full")
                self.assertTrue(selection.portable)
                self.assertEqual(
                    selection.codex,
                    path in {"Makefile", ".github/workflows/ci.yml"},
                )

    def test_unknown_source_path_falls_back_to_full(self) -> None:
        selection = self.select("scripts/new_shared_tool.py")

        self.assertEqual(selection.mode, "full")
        self.assertIn("unclassified changed path", selection.reasons[0])

    def test_unknown_automation_path_falls_back_to_full(self) -> None:
        selection = self.select(".github/workflows/new-check.yml")

        self.assertEqual(selection.mode, "full")
        self.assertIn("unclassified automation path", selection.reasons[0])

    def test_explicit_worktree_comparison_includes_tracked_and_untracked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.name", "Rootloom Test"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.email", "test@example.invalid"],
                check=True,
            )
            tracked = repository / "README.md"
            tracked.write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-qm", "initial"],
                check=True,
            )
            tracked.write_text("after\n", encoding="utf-8")
            (repository / "new.py").write_text("pass\n", encoding="utf-8")

            with mock.patch.object(self.selector, "ROOT", repository):
                paths, error = self.selector.changed_paths(
                    "HEAD",
                    None,
                    include_untracked=True,
                )

        self.assertIsNone(error)
        self.assertEqual(paths, ["README.md", "new.py"])

    def test_default_worktree_comparison_excludes_untracked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.name", "Rootloom Test"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.email", "test@example.invalid"],
                check=True,
            )
            tracked = repository / "README.md"
            tracked.write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-qm", "initial"],
                check=True,
            )
            tracked.write_text("after\n", encoding="utf-8")
            (repository / "unrelated.py").write_text("pass\n", encoding="utf-8")

            with mock.patch.object(self.selector, "ROOT", repository):
                paths, error = self.selector.changed_paths("HEAD", None)

        self.assertIsNone(error)
        self.assertEqual(paths, ["README.md"])

    def test_head_comparison_excludes_unrelated_worktree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.name", "Rootloom Test"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.email", "test@example.invalid"],
                check=True,
            )
            tracked = repository / "README.md"
            tracked.write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-qm", "initial"],
                check=True,
            )
            tracked.write_text("committed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-qm", "change"],
                check=True,
            )
            tracked.write_text("uncommitted\n", encoding="utf-8")
            (repository / "unrelated.py").write_text("pass\n", encoding="utf-8")

            with mock.patch.object(self.selector, "ROOT", repository):
                paths, error = self.selector.changed_paths("HEAD^", "HEAD")

        self.assertIsNone(error)
        self.assertEqual(paths, ["README.md"])

    def test_explicit_group_uses_selector_owned_modules(self) -> None:
        selection = self.selector.select_groups(("change", "setup", "change"))

        self.assertEqual(selection.groups, ("setup", "change"))
        self.assertEqual(
            selection.modules,
            (
                "tests.test_setup_rootloom",
                "tests.test_simple_lock",
                "tests.test_core_reset_eval",
                "tests.test_core_reset_runner",
            ),
        )

    def test_unsafe_path_falls_back_to_full(self) -> None:
        selection = self.select("../outside.py")

        self.assertEqual(selection.mode, "full")
        self.assertIn("unsafe or empty changed path", selection.reasons[0])

    def test_github_outputs_keep_canonical_full_separate_from_other_lanes(self) -> None:
        selection = self.select("README.md")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            self.selector.write_github_output(
                output,
                selection,
                canonical_full=True,
                full_matrix=False,
            )
            values = dict(
                line.split("=", 1)
                for line in output.read_text(encoding="utf-8").splitlines()
            )

        self.assertEqual(values["primary-mode"], "full")
        self.assertEqual(values["python-edge"], "false")
        self.assertEqual(values["portable"], "false")
        self.assertEqual(values["full-matrix"], "false")

    def test_full_matrix_explicitly_enables_platform_lane(self) -> None:
        selection = self.select("README.md")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            self.selector.write_github_output(
                output,
                selection,
                canonical_full=True,
                full_matrix=True,
            )
            values = dict(
                line.split("=", 1)
                for line in output.read_text(encoding="utf-8").splitlines()
            )

        self.assertEqual(values["portable"], "true")
        self.assertEqual(values["full-matrix"], "true")


if __name__ == "__main__":
    unittest.main()
