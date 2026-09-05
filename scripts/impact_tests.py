#!/usr/bin/env python3
"""Select and run Rootloom tests from changed repository paths."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
import os
import shlex
from pathlib import Path
import subprocess
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

GROUP_MODULES = {
    "setup": ("tests.test_setup_rootloom", "tests.test_simple_lock"),
    "guidance": ("tests.test_component_hook", "tests.test_seed_project_guidance"),
    "packaging": ("tests.test_host_adapters", "tests.test_portable_plugin"),
    "change": ("tests.test_core_reset_eval", "tests.test_core_reset_runner"),
    "evidence": ("tests.test_engineering_change", "tests.test_evidence_orchestrator"),
    "memory": ("tests.test_project_memory",),
    "web": ("tests.test_web_telemetry",),
}
GROUP_ORDER = tuple(GROUP_MODULES)
PORTABLE_GROUPS = {"setup", "guidance", "packaging", "evidence", "memory"}

TEST_GROUPS = {
    "tests/test_setup_rootloom.py": {"setup"},
    "tests/test_simple_lock.py": {"setup"},
    "tests/test_component_hook.py": {"guidance"},
    "tests/test_seed_project_guidance.py": {"guidance"},
    "tests/test_host_adapters.py": {"packaging"},
    "tests/test_portable_plugin.py": {"packaging"},
    "tests/test_core_reset_eval.py": {"change"},
    "tests/test_core_reset_runner.py": {"change"},
    "tests/test_engineering_change.py": {"evidence"},
    "tests/test_evidence_orchestrator.py": {"evidence"},
    "tests/test_project_memory.py": {"memory"},
    "tests/test_web_telemetry.py": {"web"},
}

FULL_FALLBACK_PATHS = {
    ".github/workflows/ci.yml",
    "Makefile",
    "scripts/impact_tests.py",
    "scripts/validate_repo.py",
    "tests/test_impact_tests.py",
}

DOCUMENTATION_NAMES = {
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "CONTRIBUTING.zh-CN.md",
    "DESIGN.md",
    "LICENSE",
    "PRODUCT.md",
    "README.md",
    "README.zh-CN.md",
    "SECURITY.md",
    "SUPPORT.md",
}


@dataclass(frozen=True)
class Selection:
    groups: tuple[str, ...]
    fallback_full: bool
    portable: bool
    codex: bool
    reasons: tuple[str, ...]

    @property
    def modules(self) -> tuple[str, ...]:
        return tuple(
            module
            for group in self.groups
            for module in GROUP_MODULES[group]
        )

    @property
    def portable_modules(self) -> tuple[str, ...]:
        return tuple(
            module
            for group in self.groups
            if group in PORTABLE_GROUPS
            for module in GROUP_MODULES[group]
        )

    @property
    def mode(self) -> str:
        if self.fallback_full:
            return "full"
        if self.groups:
            return "focused"
        return "validate"


def normalize_path(raw_path: str) -> str | None:
    path = raw_path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if not path or path.startswith("/"):
        return None
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return path


def select_paths(paths: Iterable[str]) -> Selection:
    groups: set[str] = set()
    reasons: list[str] = []
    fallback_full = False
    codex = False

    for raw_path in paths:
        path = normalize_path(raw_path)
        if path is None:
            fallback_full = True
            reasons.append(f"unsafe or empty changed path: {raw_path!r}")
            continue
        if path in FULL_FALLBACK_PATHS:
            fallback_full = True
            if path in {".github/workflows/ci.yml", "Makefile"}:
                codex = True
            reasons.append(f"shared test infrastructure: {path}")
            continue
        if path in TEST_GROUPS:
            groups.update(TEST_GROUPS[path])
            continue
        if path in {
            "tests/compatibility_smoke.py",
            "tests/portable_compatibility_smoke.py",
            "tests/live_smoke.py",
        }:
            codex = True
            continue
        if path.startswith("plugins/rootloom/skills/operating-coding-change/"):
            groups.update(("change", "packaging"))
        elif path.startswith("plugins/rootloom/skills/operating-code-review/"):
            groups.update(("change", "packaging"))
        elif path.startswith("plugins/rootloom/skills/project-guidance/"):
            groups.update(("guidance", "packaging"))
        elif path.startswith("plugins/rootloom/skills/setup-rootloom/"):
            groups.add("setup")
            codex = True
        elif path.startswith("plugins/rootloom/resources/evidence/"):
            groups.add("evidence")
        elif path.startswith("plugins/rootloom/resources/contracts/"):
            groups.add("change")
        elif path.startswith("plugins/rootloom/assets/system/"):
            groups.update(("setup", "change"))
            codex = True
        elif path.startswith("plugins/rootloom/hooks/"):
            groups.add("guidance")
            codex = True
        elif path == "plugins/rootloom/lib/rootloom_lock.py":
            groups.update(("setup", "guidance", "packaging"))
        elif path == "plugins/rootloom/lib/rootloom_paths.py":
            groups.update(("setup", "evidence"))
        elif path.startswith("plugins/rootloom/lib/"):
            fallback_full = True
            reasons.append(f"unclassified shared Core library: {path}")
        elif path.startswith("plugins/rootloom/.codex-plugin/"):
            groups.update(("setup", "packaging"))
            codex = True
        elif path.startswith("plugins/rootloom/assets/"):
            groups.add("setup")
            codex = True
        elif path.startswith("portable/rootloom/skills/"):
            groups.add("packaging")
        elif path == "portable/rootloom/plugin.json":
            groups.add("packaging")
            codex = True
        elif path.startswith("portable/rootloom/"):
            groups.add("packaging")
        elif path.startswith("adapters/rootloom/"):
            groups.add("packaging")
        elif path.startswith("experiments/rootloom-memory/"):
            groups.add("memory")
        elif path.startswith("evals/core-reset/"):
            groups.add("change")
        elif path in {
            "scripts/sync_host_adapters.py",
            "scripts/sync_portable_plugin.py",
        }:
            groups.add("packaging")
        elif path == "scripts/verify_vibeloft_runtime.py":
            groups.add("web")
        elif path == "index.html" or path.startswith("site/"):
            groups.add("web")
        elif path == ".github/workflows/codex-compatibility.yml":
            codex = True
        elif path == ".github/workflows/pages.yml":
            groups.add("web")
        elif path == ".github/workflows/release-evidence.yml":
            groups.update(("change", "web"))
        elif path.startswith(".github/workflows/") or path.startswith(
            ".github/actions/"
        ):
            fallback_full = True
            reasons.append(f"unclassified automation path: {path}")
        elif path.startswith(".github/"):
            pass
        elif (
            path in DOCUMENTATION_NAMES
            or path.startswith("docs/")
            or path.startswith("assets/")
        ):
            pass
        else:
            fallback_full = True
            reasons.append(f"unclassified changed path: {path}")

    ordered_groups = tuple(group for group in GROUP_ORDER if group in groups)
    return Selection(
        groups=ordered_groups,
        fallback_full=fallback_full,
        portable=fallback_full or bool(groups & PORTABLE_GROUPS),
        codex=codex,
        reasons=tuple(reasons),
    )


def select_groups(groups: Iterable[str]) -> Selection:
    selected = set(groups)
    ordered_groups = tuple(group for group in GROUP_ORDER if group in selected)
    return Selection(
        groups=ordered_groups,
        fallback_full=False,
        portable=bool(selected & PORTABLE_GROUPS),
        codex=False,
        reasons=(),
    )


def git_path_output(argv: list[str]) -> tuple[list[str], str | None]:
    completed = subprocess.run(
        argv,
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        return [], f"{' '.join(argv[:2])} failed: {detail or completed.returncode}"
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    ], None


def changed_paths(
    base: str | None,
    head: str | None,
    *,
    include_untracked: bool = False,
) -> tuple[list[str], str | None]:
    if not base or set(base) == {"0"}:
        return [], "comparison base is unavailable"
    comparison = [
        "git",
        "diff",
        "--name-only",
        "--no-renames",
        "--diff-filter=ACDMRTUXB",
        "-z",
        base,
    ]
    if head is not None:
        comparison.append(head)
    paths, error = git_path_output(comparison)
    if error is not None or head is not None or not include_untracked:
        return paths, error
    untracked, error = git_path_output(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"]
    )
    if error is not None:
        return [], error
    return list(dict.fromkeys((*paths, *untracked))), None


def resolve_selection(args: argparse.Namespace) -> Selection:
    if args.group:
        return select_groups(args.group)
    if args.path:
        return select_paths(args.path)
    paths, error = changed_paths(
        args.base,
        args.head,
        include_untracked=args.include_untracked,
    )
    if error is not None:
        return Selection((), True, True, False, (error,))
    return select_paths(paths)


def write_github_output(
    output_path: Path,
    selection: Selection,
    *,
    canonical_full: bool,
    full_matrix: bool,
) -> None:
    primary_mode = "full" if canonical_full else selection.mode
    python_edge = not full_matrix and (selection.fallback_full or bool(selection.modules))
    portable = full_matrix or selection.portable
    lines = (
        f"primary-mode={primary_mode}",
        f"python-edge={str(python_edge).lower()}",
        f"portable={str(portable).lower()}",
        f"codex={str(selection.codex).lower()}",
        f"full-matrix={str(full_matrix).lower()}",
    )
    with output_path.open("a", encoding="utf-8") as output:
        output.write("\n".join(lines) + "\n")


def run_command(argv: list[str]) -> int:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(argv, cwd=ROOT, env=environment, check=False).returncode


def test_commands(selection: Selection, args: argparse.Namespace) -> list[list[str]]:
    commands: list[list[str]] = []
    if args.lane == "primary":
        commands.append([sys.executable, "scripts/validate_repo.py"])
        discover = args.canonical_full or selection.fallback_full
        modules = selection.modules
    elif args.lane == "python":
        discover = selection.fallback_full
        modules = selection.modules
    else:
        discover = False
        modules = (
            tuple(
                module
                for group in GROUP_ORDER
                if group in PORTABLE_GROUPS
                for module in GROUP_MODULES[group]
            )
            if args.full_matrix or selection.fallback_full
            else selection.portable_modules
        )
    if discover:
        commands.append(
            [
                sys.executable, "-m", "unittest", "discover",
                "-s", "tests", "-p", "test_*.py", "-v",
            ]
        )
    elif modules:
        commands.append([sys.executable, "-m", "unittest", "-v", *modules])
    return commands


def report_selection(selection: Selection, args: argparse.Namespace) -> None:
    report = {
        "mode": "full" if args.canonical_full and args.lane == "primary" else selection.mode,
        "groups": list(selection.groups),
        "lane": args.lane,
        "portable": selection.portable,
        "codex": selection.codex,
        "reasons": list(selection.reasons),
        "commands": test_commands(selection, args),
    }
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2), flush=True)
        return
    print(
        "Impact selection:",
        f"mode={report['mode']}",
        f"groups={','.join(selection.groups) or 'none'}",
        f"lane={args.lane}",
        f"portable={selection.portable}",
        f"codex={selection.codex}",
        flush=True,
    )
    for reason in selection.reasons:
        print(f"Impact fallback: {reason}", file=sys.stderr, flush=True)
    if args.command == "select":
        for command in report["commands"]:
            print(f"Planned: {shlex.join(command)}", flush=True)


def run_tests(selection: Selection, args: argparse.Namespace) -> int:
    report_selection(selection, args)
    commands = test_commands(selection, args)
    if not commands:
        print("No impact-scoped checks selected.", flush=True)
    for command in commands:
        print(f"Running: {shlex.join(command)}", flush=True)
        result = run_command(command)
        if result != 0:
            return result
    return 0


def boolean(value: str) -> bool:
    if value not in {"true", "false"}:
        raise argparse.ArgumentTypeError("expected true or false")
    return value == "true"


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    subparsers = cli.add_subparsers(dest="command", required=True)
    for command in ("select", "run"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--base")
        subparser.add_argument("--head")
        subparser.add_argument("--path", action="append")
        subparser.add_argument("--group", action="append", choices=GROUP_ORDER)
        subparser.add_argument("--include-untracked", action="store_true")
        subparser.add_argument("--canonical-full", type=boolean, default=False)
        subparser.add_argument("--full-matrix", type=boolean, default=False)
        subparser.add_argument(
            "--lane", choices=("primary", "python", "portable"), default="primary"
        )
        if command == "select":
            subparser.add_argument("--github-output", type=Path)
            subparser.add_argument(
                "--json", action="store_true",
                help="Print the planned checks as JSON without running them",
            )
    return cli


def main() -> int:
    args = parser().parse_args()
    selection = resolve_selection(args)
    if args.command == "select":
        if args.github_output is not None:
            write_github_output(
                args.github_output,
                selection,
                canonical_full=args.canonical_full,
                full_matrix=args.full_matrix,
            )
        report_selection(selection, args)
        return 0
    return run_tests(selection, args)


if __name__ == "__main__":
    raise SystemExit(main())
