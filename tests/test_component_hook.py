from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "plugins" / "rootloom" / "hooks" / "run_component_hook.py"
SPEC = importlib.util.spec_from_file_location("run_component_hook", SCRIPT)
assert SPEC and SPEC.loader
component_hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(component_hook)
LIVE_SPEC = importlib.util.spec_from_file_location("live_smoke", REPO_ROOT / "tests" / "live_smoke.py")
assert LIVE_SPEC and LIVE_SPEC.loader
live_smoke = importlib.util.module_from_spec(LIVE_SPEC)
LIVE_SPEC.loader.exec_module(live_smoke)


class ComponentHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="component-hook-test-", dir=Path.home())
        self.addCleanup(self.temp_dir.cleanup)
        self.codex_home = Path(self.temp_dir.name) / ".codex"
        self.policy = self.codex_home / ".rootloom" / "components.json"

    def write_policy(self, project: bool) -> None:
        self.policy.parent.mkdir(parents=True, exist_ok=True)
        self.policy.write_text(
            json.dumps(
                {
                    "hooks": {
                        "project-guidance-hook": project,
                    },
                    "managed_by": component_hook.MANAGED_BY,
                    "version": 1,
                    "selected_capabilities": [],
                    "selected_components": [],
                }
            ),
            encoding="utf-8",
        )

    def test_absent_policy_disables_all_hooks(self) -> None:
        for name in component_hook.HOOK_COMMANDS:
            enabled, error = component_hook.hook_enabled(name, self.policy)
            self.assertFalse(enabled)
            self.assertIsNone(error)

    def test_managed_policy_controls_project_hook(self) -> None:
        self.write_policy(project=True)
        self.assertEqual(
            component_hook.hook_enabled("project-guidance-hook", self.policy),
            (True, None),
        )

    def test_policy_version_must_be_exact_integer_one(self) -> None:
        for version in (0, "1", 999, None):
            with self.subTest(version=version):
                self.write_policy(project=True)
                payload = json.loads(self.policy.read_text(encoding="utf-8"))
                if version is None:
                    payload.pop("version")
                else:
                    payload["version"] = version
                self.policy.write_text(json.dumps(payload), encoding="utf-8")

                enabled, error = component_hook.hook_enabled(
                    "project-guidance-hook", self.policy
                )

                self.assertFalse(enabled)
                self.assertIn("version must be the integer 1", error or "")

    def test_invalid_or_symlinked_policy_fails_closed(self) -> None:
        self.policy.parent.mkdir(parents=True)
        self.policy.write_text("{}", encoding="utf-8")
        enabled, error = component_hook.hook_enabled("project-guidance-hook", self.policy)
        self.assertFalse(enabled)
        self.assertIn("not a managed", error or "")

        outside = Path(self.temp_dir.name) / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        self.policy.unlink()
        self.policy.symlink_to(outside)
        enabled, error = component_hook.hook_enabled("project-guidance-hook", self.policy)
        self.assertFalse(enabled)
        self.assertIn("symbolic link", error or "")

        self.policy.unlink()
        self.policy.parent.rmdir()
        outside_dir = Path(self.temp_dir.name) / "outside-policy-dir"
        outside_dir.mkdir()
        self.policy.parent.symlink_to(outside_dir, target_is_directory=True)
        enabled, error = component_hook.hook_enabled("project-guidance-hook", self.policy)
        self.assertFalse(enabled)
        self.assertIn("symbolic link", error or "")

    def test_disabled_hook_exits_without_invoking_handler(self) -> None:
        self.write_policy(project=False)
        env = os.environ.copy()
        env["CODEX_HOME"] = str(self.codex_home)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "project-guidance-hook"],
            input=json.dumps({"cwd": str(self.temp_dir.name), "source": "startup"}),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, "")

    def test_live_smoke_requires_read_only_context_and_successful_setup(self) -> None:
        for behavior in ("context", "guidance-write", "readme-write", "wrong-reply", "setup-failure"):
            with self.subTest(behavior=behavior):
                model_calls = []

                def fake_run(argv, *, env, cwd, timeout=60):
                    code, stdout = 0, ""
                    home = Path(env["CODEX_HOME"]) if "CODEX_HOME" in env else None
                    if argv[:2] == ["git", "init"]:
                        return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=True)
                    if argv[:3] == ["codex", "plugin", "list"]:
                        stdout = json.dumps({"installed": [{
                            "pluginId": live_smoke.PLUGIN_ID,
                            "source": {"path": str(Path(self.temp_dir.name) / "plugin")},
                        }]})
                    elif argv[0] == "python3" and "apply" in argv:
                        if behavior == "setup-failure":
                            code = 1
                        else:
                            (home / "AGENTS.md").write_text("global fixture")
                    elif argv[0] == "python3" and "rollback" in argv:
                        (home / "AGENTS.md").unlink()
                    elif argv[:2] == ["codex", "exec"]:
                        model_calls.append(argv)
                        project = Path(argv[argv.index("-C") + 1])
                        message = Path(argv[argv.index("--output-last-message") + 1])
                        message.write_text(
                            "wrong project" if behavior == "wrong-reply" else "CONTEXT_OK: Live sample"
                        )
                        if behavior == "guidance-write":
                            (project / "AGENTS.md").write_text("unexpected persistence")
                        elif behavior == "readme-write":
                            (project / "README.md").write_text("changed fixture")
                    return subprocess.CompletedProcess(argv, code, stdout, "")

                output = io.StringIO()
                with (
                    mock.patch.object(live_smoke.Path, "home", return_value=Path(self.temp_dir.name)),
                    mock.patch.object(live_smoke, "run", side_effect=fake_run),
                    redirect_stdout(output),
                ):
                    code = live_smoke.main()
                self.assertEqual(code, 0 if behavior == "context" else 1)
                self.assertEqual(json.loads(output.getvalue())["passed"], behavior == "context")
                self.assertEqual(len(model_calls), 0 if behavior == "setup-failure" else 1)


if __name__ == "__main__":
    unittest.main()
