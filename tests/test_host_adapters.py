from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_host_adapters as syncer  # noqa: E402


ADAPTERS = ROOT / "adapters" / "rootloom"
CANONICAL_SCRIPT = (
    ROOT
    / "plugins"
    / "rootloom"
    / "skills"
    / "project-guidance"
    / "scripts"
    / "seed_project_guidance.py"
)
CANONICAL_LOCK = ROOT / "plugins" / "rootloom" / "lib" / "rootloom_lock.py"


class HostAdapterTests(unittest.TestCase):
    def test_checked_in_adapters_match_deterministic_source(self) -> None:
        self.assertEqual(syncer.check(ADAPTERS), [])

    def test_generator_rejects_stale_unexpected_and_symlinked_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-adapters-") as temporary:
            output = Path(temporary) / "rootloom"
            syncer.write(output)
            self.assertEqual(syncer.check(output), [])

            config = output / "cursor" / "template" / ".cursor" / "hooks.json"
            config.write_text("{}\n", encoding="utf-8")
            self.assertTrue(any("stale" in error for error in syncer.check(output)))
            syncer.write(output)

            unexpected = output / "unexpected.txt"
            unexpected.write_text("unexpected\n", encoding="utf-8")
            self.assertTrue(any("unexpected" in error for error in syncer.check(output)))
            with self.assertRaisesRegex(ValueError, "unexpected files"):
                syncer.write(output)

        with tempfile.TemporaryDirectory(prefix="rootloom-adapters-") as temporary:
            target = Path(temporary) / "target"
            target.mkdir()
            link = Path(temporary) / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"filesystem cannot create directory symlink: {exc}")
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                syncer.write(link)

    def test_generator_rejects_symlinked_source_ancestor(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rootloom-adapter-source-") as temporary:
            temporary_root = Path(temporary)
            source_root = temporary_root / "source-root"
            outside_plugins = temporary_root / "outside-plugins"
            source_root.mkdir()
            outside_plugin = outside_plugins / "rootloom"
            external_script = (
                outside_plugin
                / "skills/project-guidance/scripts/seed_project_guidance.py"
            )
            external_lock = outside_plugin / "lib/rootloom_lock.py"
            external_script.parent.mkdir(parents=True)
            external_lock.parent.mkdir(parents=True)
            external_script.write_text("# external script\n", encoding="utf-8")
            external_lock.write_text("# external lock\n", encoding="utf-8")
            try:
                (source_root / "plugins").symlink_to(
                    outside_plugins, target_is_directory=True
                )
            except OSError as exc:
                self.skipTest(f"filesystem cannot create directory symlink: {exc}")

            with (
                mock.patch.object(syncer, "ROOT", source_root),
                mock.patch.object(
                    syncer, "SOURCE_PLUGIN", source_root / "plugins/rootloom"
                ),
                mock.patch.object(
                    syncer,
                    "SOURCE_SCRIPT",
                    source_root
                    / "plugins/rootloom/skills/project-guidance/scripts/seed_project_guidance.py",
                ),
                mock.patch.object(
                    syncer,
                    "SOURCE_LOCK",
                    source_root / "plugins/rootloom/lib/rootloom_lock.py",
                ),
            ):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    syncer.expected_files()

    def test_configs_use_exact_host_events_commands_and_timeouts(self) -> None:
        cursor = json.loads(
            (ADAPTERS / "cursor/template/.cursor/hooks.json").read_text(
                encoding="utf-8"
            )
        )
        shared = json.loads(
            (
                ADAPTERS
                / "vscode-copilot/template/.github/hooks/rootloom.json"
            ).read_text(encoding="utf-8")
        )
        kiro = json.loads(
            (
                ADAPTERS
                / "kiro/template/.kiro/hooks/rootloom-session-context.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(cursor["version"], 1)
        self.assertEqual(set(cursor["hooks"]), {"sessionStart"})
        self.assertEqual(cursor["hooks"]["sessionStart"][0]["timeout"], 10)
        self.assertIn("--protocol cursor --allow-untrusted", cursor["hooks"]["sessionStart"][0]["command"])

        self.assertEqual(set(shared), {"version", "hooks"})
        self.assertIs(type(shared["version"]), int)
        self.assertEqual(shared["version"], 1)
        self.assertEqual(set(shared["hooks"]), {"sessionStart"})
        shared_hook = shared["hooks"]["sessionStart"][0]
        self.assertEqual(shared_hook["type"], "command")
        self.assertEqual(shared_hook["timeout"], 10)
        self.assertIn("--protocol auto --allow-untrusted", shared_hook["command"])

        self.assertEqual(kiro["version"], "v1")
        self.assertEqual(len(kiro["hooks"]), 1)
        self.assertEqual(kiro["hooks"][0]["trigger"], "SessionStart")
        self.assertEqual(kiro["hooks"][0]["timeout"], 10)
        self.assertEqual(kiro["hooks"][0]["action"]["type"], "command")
        self.assertIn("--protocol kiro --allow-untrusted", kiro["hooks"][0]["action"]["command"])

        for command in (
            cursor["hooks"]["sessionStart"][0]["command"],
            shared_hook["command"],
            kiro["hooks"][0]["action"]["command"],
        ):
            self.assertIn('".rootloom/rootloom-adapter/seed_project_guidance.py"', command)
            self.assertEqual(shlex.split(command)[0:2], ["python3", "-B"])

    def test_every_adapter_vendors_canonical_runtime_bytes(self) -> None:
        for template in ("cursor/template", "vscode-copilot/template", "kiro/template"):
            with self.subTest(template=template):
                runtime = ADAPTERS / template / ".rootloom/rootloom-adapter"
                self.assertEqual(
                    (runtime / "seed_project_guidance.py").read_bytes(),
                    CANONICAL_SCRIPT.read_bytes(),
                )
                self.assertEqual(
                    (runtime / "rootloom_lock.py").read_bytes(),
                    CANONICAL_LOCK.read_bytes(),
                )
                self.assertFalse((runtime / "seed_project_guidance.py").is_symlink())
                self.assertFalse((runtime / "rootloom_lock.py").is_symlink())

    def test_capability_contract_declares_baseline_and_pending_runtime(self) -> None:
        contract = json.loads(
            (ADAPTERS / "capabilities.json").read_text(encoding="utf-8")
        )
        self.assertEqual(contract["format"], "rootloom-host-capabilities-v1")
        self.assertEqual(
            set(contract["baseline"]["skills"]),
            {
                "operating-coding-change",
                "operating-code-review",
                "project-guidance",
            },
        )
        self.assertEqual(contract["baseline"]["session_context"]["access"], "read-only")
        self.assertEqual(contract["baseline"]["session_context"]["maximum_bytes"], 4096)
        for host in ("cursor", "vscode", "github-copilot", "kiro"):
            self.assertEqual(contract["hosts"][host]["runtime_status"], "pending")
            self.assertEqual(
                contract["hosts"][host]["verification"],
                "static-and-synthetic-only",
            )
        self.assertEqual(contract["non_unified"]["setup"], "codex-native-only")
        self.assertEqual(
            contract["non_unified"]["evidence_runtime"],
            "unavailable-in-portable-package",
        )
        self.assertEqual(
            contract["non_unified"]["permission_enforcement"], "host-owned"
        )

    def test_adapter_commands_are_read_only_and_share_identical_context(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="rootloom adapter path with spaces-", dir=Path.home()
        ) as temporary:
            base = Path(temporary)
            contexts: dict[str, str] = {}
            cases = {
                "cursor": (
                    "cursor/template",
                    ".cursor/hooks.json",
                    {"cwd": None, "source": "startup"},
                ),
                "vscode": (
                    "vscode-copilot/template",
                    ".github/hooks/rootloom.json",
                    {"cwd": None, "hook_event_name": "SessionStart", "session_id": "vs"},
                ),
                "copilot": (
                    "vscode-copilot/template",
                    ".github/hooks/rootloom.json",
                    {"cwd": None, "sessionId": "copilot"},
                ),
                "kiro": (
                    "kiro/template",
                    ".kiro/hooks/rootloom-session-context.json",
                    {"cwd": None},
                ),
            }
            for host, (template, config_path, event) in cases.items():
                project = base / host / "consumer repository"
                source = ADAPTERS / template
                shutil.copytree(source, project)
                shadow = project.parent / "lib" / "rootloom_lock.py"
                shadow.parent.mkdir()
                shadow.write_text(
                    "raise RuntimeError('external lock shadow loaded')\n",
                    encoding="utf-8",
                )
                subprocess.run(["git", "init", "-q", str(project)], check=True)
                (project / "README.md").write_text(
                    "# Shared Fixture\n\nA portable adapter fixture.\n",
                    encoding="utf-8",
                )
                (project / "package.json").write_text(
                    '{"name":"shared-fixture","scripts":{"test":"unit"}}\n',
                    encoding="utf-8",
                )
                event["cwd"] = str(project)
                config = json.loads((project / config_path).read_text(encoding="utf-8"))
                if host == "cursor":
                    command = config["hooks"]["sessionStart"][0]["command"]
                elif host in {"vscode", "copilot"}:
                    command = config["hooks"]["sessionStart"][0]["command"]
                else:
                    command = config["hooks"][0]["action"]["command"]
                completed = subprocess.run(
                    command,
                    cwd=project,
                    input=json.dumps(event),
                    capture_output=True,
                    text=True,
                    shell=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                if host == "cursor":
                    contexts[host] = json.loads(completed.stdout)["additional_context"]
                elif host == "vscode":
                    contexts[host] = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
                elif host == "copilot":
                    contexts[host] = json.loads(completed.stdout)["additionalContext"]
                else:
                    contexts[host] = completed.stdout.rstrip("\n")
                self.assertFalse((project / "AGENTS.md").exists())
                self.assertFalse(any(project.rglob("__pycache__")))

            self.assertEqual(len(set(contexts.values())), 1, contexts)

    def test_malformed_oversize_plan_and_missing_interpreter_are_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="rootloom adapter failures-", dir=Path.home()
        ) as temporary:
            project = Path(temporary) / "consumer"
            shutil.copytree(ADAPTERS / "cursor/template", project)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            config = json.loads(
                (project / ".cursor/hooks.json").read_text(encoding="utf-8")
            )
            command = config["hooks"]["sessionStart"][0]["command"]

            runtime_script = project / ".rootloom/rootloom-adapter/seed_project_guidance.py"
            oversized = '{"padding":"' + ("x" * (1024 * 1024)) + '"}'
            for protocol in ("cursor", "copilot", "auto", "kiro"):
                argv = [
                    sys.executable,
                    "-B",
                    str(runtime_script),
                    "hook",
                    "--protocol",
                    protocol,
                    "--allow-untrusted",
                ]
                for label, payload, marker in (
                    ("malformed", "{not-json", "input error"),
                    ("oversize", oversized, "exceeded 1 MiB"),
                ):
                    with self.subTest(protocol=protocol, input=label):
                        completed = subprocess.run(
                            argv,
                            cwd=project,
                            input=payload,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        self.assertEqual(completed.returncode, 0)
                        self.assertEqual(completed.stdout, "")
                        self.assertIn(marker, completed.stderr)

            plan = subprocess.run(
                command,
                cwd=project,
                input=json.dumps(
                    {"cwd": str(project), "permission_mode": "plan"}
                ),
                capture_output=True,
                text=True,
                shell=True,
                check=False,
            )
            self.assertEqual(plan.returncode, 0)
            self.assertEqual(plan.stdout, "")

            missing = subprocess.run(
                command,
                cwd=project,
                input=json.dumps({"cwd": str(project)}),
                capture_output=True,
                text=True,
                shell=True,
                env={**os.environ, "PATH": "/definitely/missing"},
                check=False,
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertFalse((project / "AGENTS.md").exists())


if __name__ == "__main__":
    unittest.main()
