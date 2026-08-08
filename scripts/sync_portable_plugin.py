#!/usr/bin/env python3
"""Build or verify the checked-in Agent Plugins portable package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE_BOUNDARY = ROOT
SOURCE_PLUGIN = ROOT / "plugins" / "rootloom"
SOURCE_MANIFEST = SOURCE_PLUGIN / ".codex-plugin" / "plugin.json"
DEFAULT_OUTPUT = ROOT / "portable" / "rootloom"
PORTABLE_SKILL_FILES = {
    "operating-code-review": (
        Path("SKILL.md"),
        Path("references/data-and-migration-review.md"),
        Path("references/dependency-and-release-review.md"),
        Path("references/security-review.md"),
        Path("references/ui-review.md"),
    ),
    "operating-coding-change": (
        Path("SKILL.md"),
        Path("references/evidence-contract.md"),
        Path("references/evidence-mode.md"),
        Path("references/external-actions.md"),
        Path("references/governed-change.md"),
        Path("references/verification-contract.md"),
    ),
    "project-guidance": (
        Path("SKILL.md"),
        Path("references/semantic-refinement.md"),
        Path("scripts/seed_project_guidance.py"),
    ),
}
PORTABLE_SKILLS = tuple(PORTABLE_SKILL_FILES)
PROJECT_GUIDANCE_LOCK = SOURCE_PLUGIN / "lib" / "rootloom_lock.py"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def validate_source_path(path: Path, boundary: Path) -> None:
    if boundary.is_symlink():
        raise ValueError(f"portable source boundary must not be a symlink: {boundary}")
    try:
        relative = path.relative_to(boundary)
    except ValueError as exc:
        raise ValueError(f"portable source escapes its boundary: {path}") from exc
    current = boundary
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"portable source must not traverse a symlink: {current}")
    resolved_boundary = boundary.resolve(strict=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(resolved_boundary):
        raise ValueError(f"portable source escapes its boundary: {path}")


def checked_source_directory(path: Path, boundary: Path) -> None:
    validate_source_path(path, boundary)
    if not path.is_dir():
        raise ValueError(f"portable source must be a directory: {path}")


def checked_source_bytes(path: Path, boundary: Path) -> bytes:
    validate_source_path(path, boundary)
    if not path.is_file():
        raise ValueError(f"portable source must be a regular file: {path}")
    return path.read_bytes()


def portable_manifest() -> dict[str, object]:
    source = json.loads(
        checked_source_bytes(SOURCE_MANIFEST, SOURCE_PLUGIN).decode("utf-8")
    )
    return {
        "$schema": SCHEMA,
        "name": source["name"],
        "version": source["version"],
        "description": (
            "Portable Rootloom Agent Skills for inspectable code changes and "
            "evidence-backed review with bounded project guidance."
        ),
        "author": source["author"],
        "homepage": source["homepage"],
        "repository": source["repository"],
        "license": source["license"],
        "keywords": [
            "rootloom",
            "agent-plugins",
            "agent-skills",
            "code-review",
            "personal-engineering",
            "project-guidance",
            "risk-analysis",
            "root-cause-analysis",
            "software-engineering",
            "verification",
        ],
    }


def portable_skill_files(
    source_root: Path, approved_files: tuple[Path, ...]
) -> dict[Path, bytes]:
    """Return approved portable Skill files and reject source-tree drift."""

    approved = set(approved_files)
    discovered: set[Path] = set()
    for source in sorted(source_root.rglob("*")):
        validate_source_path(source, source_root)
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        if "agents" in relative.parts or "__pycache__" in relative.parts:
            continue
        discovered.add(relative)

    unexpected = discovered - approved
    if unexpected:
        joined = ", ".join(path.as_posix() for path in sorted(unexpected))
        raise ValueError(f"unapproved portable source file(s): {joined}")
    missing = approved - discovered
    if missing:
        joined = ", ".join(path.as_posix() for path in sorted(missing))
        raise ValueError(f"missing approved portable source file(s): {joined}")

    return {
        relative: checked_source_bytes(source_root / relative, source_root)
        for relative in approved_files
    }


def expected_files() -> dict[Path, bytes]:
    checked_source_directory(SOURCE_PLUGIN, SOURCE_BOUNDARY)
    checked_source_directory(SOURCE_PLUGIN / "skills", SOURCE_PLUGIN)
    manifest = json.dumps(portable_manifest(), indent=2, ensure_ascii=False) + "\n"
    expected = {
        Path("plugin.json"): manifest.encode("utf-8"),
        Path("LICENSE"): checked_source_bytes(ROOT / "LICENSE", ROOT),
    }
    for skill_name in PORTABLE_SKILLS:
        source_root = SOURCE_PLUGIN / "skills" / skill_name
        checked_source_directory(source_root, SOURCE_PLUGIN)
        for relative, content in portable_skill_files(
            source_root, PORTABLE_SKILL_FILES[skill_name]
        ).items():
            expected[Path("skills") / skill_name / relative] = content
    expected[
        Path("skills") / "project-guidance" / "scripts" / "rootloom_lock.py"
    ] = checked_source_bytes(PROJECT_GUIDANCE_LOCK, SOURCE_PLUGIN)
    return expected


def actual_files(output: Path) -> set[Path]:
    if not output.exists():
        return set()
    return {
        path.relative_to(output)
        for path in output.rglob("*")
        if path.is_file() or path.is_symlink()
    }


def validate_output_root(output: Path) -> None:
    if output.exists() and output.is_symlink():
        raise ValueError(f"portable output must not be a symlink: {output}")


def check(output: Path) -> list[str]:
    validate_output_root(output)
    expected = expected_files()
    actual = actual_files(output)
    errors: list[str] = []
    for path in sorted(set(expected) - actual):
        errors.append(f"missing portable file: {path.as_posix()}")
    for path in sorted(actual - set(expected)):
        errors.append(f"unexpected portable file: {path.as_posix()}")
    for relative in sorted(set(expected) & actual):
        target = output / relative
        if target.is_symlink():
            errors.append(f"portable file must not be a symlink: {relative.as_posix()}")
        elif target.read_bytes() != expected[relative]:
            errors.append(f"stale portable file: {relative.as_posix()}")
    return errors


def write(output: Path) -> None:
    validate_output_root(output)
    expected = expected_files()
    unexpected = actual_files(output) - set(expected)
    if unexpected:
        joined = ", ".join(path.as_posix() for path in sorted(unexpected))
        raise ValueError(f"refusing to overwrite output with unexpected files: {joined}")
    output.mkdir(parents=True, exist_ok=True)
    for relative, content in expected.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
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
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Portable Agent Plugin is synchronized: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
