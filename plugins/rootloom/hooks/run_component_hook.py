#!/usr/bin/env python3
"""Gate a bundled lifecycle Hook through the user's component policy."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


MAX_EVENT_BYTES = 1_048_576
MANAGED_BY = "rootloom:managed"
HOOK_COMMANDS = {
    "project-guidance-hook": (
        "skills/project-guidance/scripts/seed_project_guidance.py",
        "hook",
    ),
}
HOOK_TIMEOUTS = {
    "project-guidance-hook": 12,
}


def component_policy_path() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home.expanduser() / ".rootloom" / "components.json"


def hook_enabled(component: str, policy_path: Path | None = None) -> tuple[bool, str | None]:
    """Return the configured state; absent or invalid policy fails closed."""

    path = policy_path or component_policy_path()
    if path.parent.is_symlink() or path.is_symlink():
        return False, f"component policy or its state directory is a symbolic link: {path}"
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, None
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"component policy could not be read: {exc}"
    if not isinstance(payload, dict) or payload.get("managed_by") != MANAGED_BY:
        return False, "component policy is not a managed Rootloom policy"
    version = payload.get("version")
    if type(version) is not int or version != 1:
        return False, "component policy version must be the integer 1"
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict) or type(hooks.get(component)) is not bool:
        return False, f"component policy has no boolean state for {component}"
    return hooks[component], None


def hook_message(message: str) -> str:
    return json.dumps({"continue": True, "systemMessage": message}, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=sorted(HOOK_COMMANDS))
    args = parser.parse_args(argv)

    enabled, error = hook_enabled(args.component)
    if error:
        print(hook_message(f"Rootloom Hook skipped: {error}"))
        return 0
    if not enabled:
        return 0

    event = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
    if len(event) > MAX_EVENT_BYTES:
        print(hook_message("Rootloom Hook skipped: event exceeded 1 MiB"))
        return 0

    plugin_root = Path(__file__).resolve().parents[1]
    command = HOOK_COMMANDS[args.component]
    target = plugin_root / command[0]
    if target.is_symlink() or not target.is_file():
        print(hook_message(f"Rootloom Hook target is unavailable: {target}"))
        return 0

    try:
        completed = subprocess.run(
            [sys.executable, str(target), *command[1:]],
            input=event,
            capture_output=True,
            check=False,
            timeout=HOOK_TIMEOUTS[args.component],
        )
    except subprocess.TimeoutExpired:
        print(hook_message(f"Rootloom {args.component} handler timed out"))
        return 0
    if completed.stderr:
        sys.stderr.buffer.write(completed.stderr)
    if completed.returncode != 0:
        print(
            hook_message(
                f"Rootloom {args.component} handler failed with exit code "
                f"{completed.returncode}"
            )
        )
        return 0
    if completed.stdout:
        sys.stdout.buffer.write(completed.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
