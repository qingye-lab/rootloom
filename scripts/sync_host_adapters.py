#!/usr/bin/env python3
"""Build or verify opt-in consumer-repository host adapter templates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PLUGIN = ROOT / "plugins" / "rootloom"
SOURCE_SCRIPT = (
    SOURCE_PLUGIN
    / "skills"
    / "project-guidance"
    / "scripts"
    / "seed_project_guidance.py"
)
SOURCE_LOCK = SOURCE_PLUGIN / "lib" / "rootloom_lock.py"
DEFAULT_OUTPUT = ROOT / "adapters" / "rootloom"
RUNTIME_ROOT = Path(".rootloom/rootloom-adapter")
RUNTIME_SCRIPT = RUNTIME_ROOT / "seed_project_guidance.py"
RUNTIME_LOCK = RUNTIME_ROOT / "rootloom_lock.py"
TIMEOUT_SECONDS = 10


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _checked_source_bytes(path: Path) -> bytes:
    if ROOT.is_symlink():
        raise ValueError(f"adapter source boundary must not be a symlink: {ROOT}")
    try:
        root_relative = path.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"adapter source escapes its boundary: {path}") from exc
    current = ROOT
    for part in root_relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"adapter source must not traverse a symlink: {current}")
    try:
        path.relative_to(SOURCE_PLUGIN)
    except ValueError as exc:
        raise ValueError(f"adapter source escapes its plugin boundary: {path}") from exc
    resolved_root = ROOT.resolve(strict=True)
    resolved_plugin = SOURCE_PLUGIN.resolve(strict=True)
    resolved = path.resolve(strict=True)
    if not resolved_plugin.is_relative_to(resolved_root):
        raise ValueError(f"adapter plugin source escapes repository boundary: {SOURCE_PLUGIN}")
    if not resolved.is_relative_to(resolved_plugin):
        raise ValueError(f"adapter source escapes its boundary: {path}")
    if not path.is_file():
        raise ValueError(f"adapter source must be a regular file: {path}")
    return path.read_bytes()


def _command(protocol: str) -> str:
    return (
        f'python3 -B "{RUNTIME_SCRIPT.as_posix()}" hook '
        f"--protocol {protocol} --allow-untrusted"
    )


def _capability_contract() -> dict[str, object]:
    return {
        "format": "rootloom-host-capabilities-v1",
        "baseline": {
            "skills": [
                "operating-coding-change",
                "operating-code-review",
                "project-guidance",
            ],
            "session_context": {
                "access": "read-only",
                "maximum_bytes": 4096,
                "renderer": "plugins/rootloom/skills/project-guidance/scripts/seed_project_guidance.py",
                "persistence": "never",
            },
        },
        "hosts": {
            "codex": {
                "runtime_status": "native-existing",
                "event": "SessionStart",
                "protocol": "codex",
                "config": "plugins/rootloom/hooks/hooks.json",
            },
            "cursor": {
                "runtime_status": "pending",
                "verification": "static-and-synthetic-only",
                "event": "sessionStart",
                "protocol": "cursor",
                "config": "cursor/template/.cursor/hooks.json",
            },
            "vscode": {
                "runtime_status": "pending",
                "verification": "static-and-synthetic-only",
                "event": "sessionStart-translated-to-SessionStart",
                "protocol": "auto-to-vscode",
                "config": "vscode-copilot/template/.github/hooks/rootloom.json",
            },
            "github-copilot": {
                "runtime_status": "pending",
                "verification": "static-and-synthetic-only",
                "event": "sessionStart",
                "protocol": "auto-to-copilot",
                "config": "vscode-copilot/template/.github/hooks/rootloom.json",
            },
            "kiro": {
                "runtime_status": "pending",
                "verification": "static-and-synthetic-only",
                "event": "SessionStart",
                "protocol": "kiro-plain-stdout",
                "config": "kiro/template/.kiro/hooks/rootloom-session-context.json",
            },
        },
        "non_unified": {
            "setup": "codex-native-only",
            "evidence_runtime": "unavailable-in-portable-package",
            "permission_enforcement": "host-owned",
        },
    }


def expected_files() -> dict[Path, bytes]:
    script = _checked_source_bytes(SOURCE_SCRIPT)
    lock = _checked_source_bytes(SOURCE_LOCK)
    cursor = {
        "version": 1,
        "hooks": {
            "sessionStart": [
                {
                    "command": _command("cursor"),
                    "timeout": TIMEOUT_SECONDS,
                }
            ]
        },
    }
    vscode_copilot = {
        "version": 1,
        "hooks": {
            "sessionStart": [
                {
                    "type": "command",
                    "command": _command("auto"),
                    "timeout": TIMEOUT_SECONDS,
                }
            ]
        }
    }
    kiro = {
        "version": "v1",
        "hooks": [
            {
                "name": "Rootloom session context",
                "description": "Inject bounded read-only Rootloom project facts.",
                "trigger": "SessionStart",
                "action": {
                    "type": "command",
                    "command": _command("kiro"),
                },
                "timeout": TIMEOUT_SECONDS,
            }
        ],
    }
    expected = {
        Path("capabilities.json"): _json_bytes(_capability_contract()),
        Path("cursor/template/.cursor/hooks.json"): _json_bytes(cursor),
        Path("vscode-copilot/template/.github/hooks/rootloom.json"): _json_bytes(
            vscode_copilot
        ),
        Path("kiro/template/.kiro/hooks/rootloom-session-context.json"): _json_bytes(
            kiro
        ),
    }
    for template in ("cursor/template", "vscode-copilot/template", "kiro/template"):
        root = Path(template)
        expected[root / RUNTIME_SCRIPT] = script
        expected[root / RUNTIME_LOCK] = lock
    return expected


def _actual_files(output: Path) -> set[Path]:
    if not output.exists():
        return set()
    return {
        path.relative_to(output)
        for path in output.rglob("*")
        if path.is_file() or path.is_symlink()
    }


def _validate_output_root(output: Path) -> None:
    if output.exists() and output.is_symlink():
        raise ValueError(f"adapter output must not be a symlink: {output}")


def check(output: Path) -> list[str]:
    _validate_output_root(output)
    expected = expected_files()
    actual = _actual_files(output)
    errors: list[str] = []
    for relative in sorted(set(expected) - actual):
        errors.append(f"missing host adapter file: {relative.as_posix()}")
    for relative in sorted(actual - set(expected)):
        errors.append(f"unexpected host adapter file: {relative.as_posix()}")
    for relative in sorted(set(expected) & actual):
        target = output / relative
        if target.is_symlink():
            errors.append(f"host adapter file must not be a symlink: {relative.as_posix()}")
        elif target.read_bytes() != expected[relative]:
            errors.append(f"stale host adapter file: {relative.as_posix()}")
    return errors


def write(output: Path) -> None:
    _validate_output_root(output)
    expected = expected_files()
    unexpected = _actual_files(output) - set(expected)
    if unexpected:
        joined = ", ".join(path.as_posix() for path in sorted(unexpected))
        raise ValueError(f"refusing to overwrite output with unexpected files: {joined}")
    output.mkdir(parents=True, exist_ok=True)
    resolved_output = output.resolve(strict=True)
    for relative, content in expected.items():
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"host adapter path escapes output: {relative}")
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.parent.resolve(strict=True).is_relative_to(resolved_output):
            raise ValueError(f"host adapter path escapes output: {target}")
        if target.exists() and target.is_symlink():
            raise ValueError(f"refusing to replace symlink: {target}")
        target.write_bytes(content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.expanduser()
    if not output.is_absolute():
        output = Path.cwd() / output
    try:
        if args.write:
            write(output)
        errors = check(output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Rootloom host adapters are synchronized: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
