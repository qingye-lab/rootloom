#!/usr/bin/env python3
"""Exercise the isolated Agent Plugins package against the installed Codex CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


MARKETPLACE_NAME = "rootloom-portable-smoke"
PLUGIN_ID = f"rootloom@{MARKETPLACE_NAME}"
REPO_ROOT = Path(__file__).resolve().parents[1]
PORTABLE_PLUGIN = REPO_ROOT / "portable" / "rootloom"


def run(argv: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def installed_plugin_path(payload: dict[str, Any]) -> Path | None:
    for item in payload.get("installed", []):
        if item.get("pluginId") == PLUGIN_ID:
            raw = item.get("source", {}).get("path")
            return Path(raw) if raw else None
    return None


def main() -> int:
    with tempfile.TemporaryDirectory(
        prefix="rootloom-portable-compatibility-", dir=Path.home()
    ) as temporary:
        temporary_root = Path(temporary)
        codex_home = temporary_root / "codex-home"
        marketplace = temporary_root / "marketplace"
        codex_home.mkdir()
        (marketplace / ".agents" / "plugins").mkdir(parents=True)
        shutil.copytree(PORTABLE_PLUGIN, marketplace / "portable" / "rootloom")
        marketplace_manifest = {
            "name": MARKETPLACE_NAME,
            "plugins": [
                {
                    "name": "rootloom",
                    "source": {
                        "source": "local",
                        "path": "./portable/rootloom",
                    },
                    "policy": {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Productivity",
                }
            ],
        }
        (marketplace / ".agents" / "plugins" / "marketplace.json").write_text(
            json.dumps(marketplace_manifest, indent=2) + "\n", encoding="utf-8"
        )

        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        commands: dict[str, subprocess.CompletedProcess[str]] = {
            "version": run(["codex", "--version"], env=env),
            "marketplace": run(
                ["codex", "plugin", "marketplace", "add", str(marketplace), "--json"],
                env=env,
            ),
            "install": run(["codex", "plugin", "add", PLUGIN_ID, "--json"], env=env),
            "plugin_list": run(["codex", "plugin", "list", "--json"], env=env),
        }
        plugin_path: Path | None = None
        if commands["plugin_list"].returncode == 0:
            try:
                plugin_path = installed_plugin_path(
                    json.loads(commands["plugin_list"].stdout)
                )
            except json.JSONDecodeError:
                pass

        packaged_skills: list[str] = []
        guidance_probe: subprocess.CompletedProcess[str] | None = None
        if plugin_path and (plugin_path / "skills").is_dir():
            packaged_skills = sorted(
                path.name
                for path in (plugin_path / "skills").iterdir()
                if path.is_dir()
            )
            helper = (
                plugin_path
                / "skills"
                / "project-guidance"
                / "scripts"
                / "seed_project_guidance.py"
            )
            fixture = temporary_root / "repository with spaces"
            subprocess.run(["git", "init", "-q", str(fixture)], check=True)
            if helper.is_file():
                guidance_probe = subprocess.run(
                    [
                        sys.executable,
                        str(helper),
                        "probe",
                        "--cwd",
                        str(fixture),
                    ],
                    cwd=REPO_ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                commands["guidance_probe"] = guidance_probe
        failed = {
            name: {
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-500:],
                "stderr_tail": completed.stderr[-500:],
            }
            for name, completed in commands.items()
            if completed.returncode != 0
        }
        passed = (
            plugin_path is not None
            and not failed
            and (plugin_path / "plugin.json").is_file()
            and packaged_skills
            == [
                "operating-code-review",
                "operating-coding-change",
                "project-guidance",
            ]
            and not (plugin_path / ".codex-plugin").exists()
            and not (plugin_path / "hooks").exists()
            and not (plugin_path / "skills" / "setup-rootloom").exists()
            and (
                plugin_path
                / "skills"
                / "project-guidance"
                / "scripts"
                / "seed_project_guidance.py"
            ).is_file()
            and (
                plugin_path
                / "skills"
                / "project-guidance"
                / "scripts"
                / "rootloom_lock.py"
            ).is_file()
            and guidance_probe is not None
            and guidance_probe.returncode == 0
            and json.loads(guidance_probe.stdout).get("status") == "ready"
        )
        print(
            json.dumps(
                {
                    "passed": passed,
                    "codex_version": commands["version"].stdout.strip(),
                    "plugin_path": str(plugin_path) if plugin_path else None,
                    "packaged_skills": packaged_skills,
                    "failed_commands": failed,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
