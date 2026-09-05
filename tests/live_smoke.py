#!/usr/bin/env python3
"""Run an optional live Personal Core Hook smoke test."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile


PLUGIN_ID = "rootloom@rootloom"
REPO_ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str], *, env: dict[str, str], cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rootloom-live-", dir=Path.home()) as temporary:
        root = Path(temporary)
        codex_home = root / "codex-home"
        codex_home.mkdir()
        auth = Path.home() / ".codex" / "auth.json"
        if auth.is_file():
            (codex_home / "auth.json").symlink_to(auth)
        repo = root / "sample"
        repo.mkdir()
        run(["git", "init", "-q"], env=os.environ.copy(), cwd=repo)
        readme = repo / "README.md"
        readme.write_text("# Live sample\n", encoding="utf-8")

        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home)
        env["ROOTLOOM_ALLOW_UNTRUSTED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        marketplace = run(
            ["codex", "plugin", "marketplace", "add", str(REPO_ROOT), "--json"],
            env=env,
            cwd=REPO_ROOT,
        )
        install = run(
            ["codex", "plugin", "add", PLUGIN_ID, "--json"], env=env, cwd=REPO_ROOT
        )
        plugin_list = run(
            ["codex", "plugin", "list", "--json"], env=env, cwd=REPO_ROOT
        )
        plugin_path: Path | None = None
        if plugin_list.returncode == 0:
            for item in json.loads(plugin_list.stdout).get("installed", []):
                if item.get("pluginId") == PLUGIN_ID and item.get("source", {}).get("path"):
                    plugin_path = Path(item["source"]["path"])
                    break
        setup = (
            plugin_path / "skills" / "setup-rootloom" / "scripts" / "setup_rootloom.py"
            if plugin_path
            else Path("missing")
        )
        base = ["python3", str(setup), "--codex-home", str(codex_home), "--json"]
        applied = run([*base, "apply", "--preset", "personal"], env=env, cwd=REPO_ROOT)
        prerequisites = {
            "marketplace": marketplace.returncode,
            "install": install.returncode,
            "plugin_list": plugin_list.returncode,
            "setup": applied.returncode,
        }
        if plugin_path is None or any(prerequisites.values()):
            print(json.dumps({"passed": False, "prerequisite_exit_codes": prerequisites}))
            return 1
        last_message = root / "last-message.txt"
        model = run(
            [
                "codex",
                "exec",
                "--dangerously-bypass-hook-trust",
                "--ephemeral",
                "--output-last-message",
                str(last_message),
                "-C",
                str(repo),
                "Using only the Rootloom SessionStart context already supplied, reply exactly "
                "CONTEXT_OK: <project name>, replacing <project name> with the detected project name. "
                "Do not call tools or create or edit files.",
            ],
            env=env,
            cwd=repo,
            timeout=180,
        )
        reply = last_message.read_text(encoding="utf-8").strip() if last_message.is_file() else ""
        repository_unchanged = (
            {path.name for path in repo.iterdir()} == {".git", "README.md"}
            and not readme.is_symlink()
            and readme.read_text(encoding="utf-8") == "# Live sample\n"
        )
        rolled_back = run([*base, "rollback"], env=env, cwd=REPO_ROOT)
        passed = (
            model.returncode == 0
            and repository_unchanged
            and reply == "CONTEXT_OK: Live sample"
            and rolled_back.returncode == 0
            and not (codex_home / "AGENTS.md").exists()
        )
        print(
            json.dumps(
                {
                    "passed": passed,
                    "plugin_path": str(plugin_path) if plugin_path else None,
                    "model_returncode": model.returncode,
                    "repository_unchanged": repository_unchanged,
                    "context_reply": reply,
                    "model_stdout_tail": model.stdout[-500:],
                    "model_stderr_tail": model.stderr[-500:],
                },
                indent=2,
            )
        )
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
