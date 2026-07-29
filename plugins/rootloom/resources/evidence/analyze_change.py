#!/usr/bin/env python3
"""Analyze a planned or current change for risk and verification needs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from runner.contracts import RISK_LEVELS
from runner.baseline import baseline_payload, repository_identity, write_new_baseline
from runner.evidence_paths import (
    validate_no_symlink_chain,
    validate_outside_repository_storage,
)
from runner.intelligence import analyze_change
from runner.state import (
    CaptureDeadline,
    DEFAULT_MAX_CAPTURE_SECONDS,
    DEFAULT_MAX_GIT_SECONDS,
    DEFAULT_MAX_SENSITIVE_PATHS,
    repository_snapshot,
    stable_repository_capture,
    tracked_patch,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--task", default="")
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--declared-risk", choices=RISK_LEVELS)
    parser.add_argument("--sensitive-path", action="append", default=[])
    parser.add_argument("--write-baseline", type=Path)
    parser.add_argument(
        "--max-capture-seconds",
        type=float,
        default=DEFAULT_MAX_CAPTURE_SECONDS,
    )
    parser.add_argument(
        "--max-git-seconds",
        type=float,
        default=DEFAULT_MAX_GIT_SECONDS,
    )
    parser.add_argument(
        "--max-sensitive-paths",
        type=int,
        default=DEFAULT_MAX_SENSITIVE_PATHS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not math.isfinite(args.max_capture_seconds) or args.max_capture_seconds <= 0:
        raise SystemExit("capture time budget must be finite and positive")
    if not math.isfinite(args.max_git_seconds) or args.max_git_seconds <= 0:
        raise SystemExit("Git time budget must be finite and positive")
    if args.max_sensitive_paths <= 0:
        raise SystemExit("sensitive path budget must be positive")
    repo = args.repo.expanduser().resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"not a Git repository: {repo}")
    if args.write_baseline:
        try:
            baseline_lexical = validate_no_symlink_chain(
                args.write_baseline,
                label="baseline output",
                leaf_may_be_missing=True,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        try:
            identity = repository_identity(
                repo,
                max_git_seconds=args.max_git_seconds,
            )
            baseline_path = validate_outside_repository_storage(
                baseline_lexical,
                repository_roots=(
                    Path(identity["worktree"]),
                    Path(identity["git_common_dir"]),
                ),
                label="baseline output",
            )
        except (OSError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
    captured_git = None
    try:
        if args.write_baseline:
            (
                snapshot,
                _untracked_patch,
                patch,
                captured_git,
                _capture_duration_seconds,
                _reviewable_metadata,
            ) = stable_repository_capture(
                repo,
                extra_sensitive=args.sensitive_path,
                max_capture_seconds=args.max_capture_seconds,
                max_git_seconds=args.max_git_seconds,
                max_sensitive_paths=args.max_sensitive_paths,
            )
        else:
            capture_deadline = CaptureDeadline(args.max_capture_seconds)
            snapshot, _untracked_patch = repository_snapshot(
                repo,
                extra_sensitive=args.sensitive_path,
                max_git_seconds=args.max_git_seconds,
                max_sensitive_paths=args.max_sensitive_paths,
                capture_deadline=capture_deadline,
            )
            sensitive = [item["path"] for item in snapshot["sensitive_paths"]]
            patch = tracked_patch(
                repo,
                sensitive_paths=sensitive,
                max_git_seconds=args.max_git_seconds,
                capture_deadline=capture_deadline,
            )
            capture_deadline.checkpoint()
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    assessment = analyze_change(
        repo,
        task=args.task,
        anticipated_paths=args.path,
        changes=snapshot["changes"],
        tracked_patch=(
            patch
            + (b"\n" if patch and _untracked_patch else b"")
            + _untracked_patch
        ),
        declared_risk=args.declared_risk,
        allow_repository_reads=not bool(
            snapshot["bounds"].get("sensitive_change_quarantine")
        ),
    )
    if args.write_baseline:
        try:
            baseline_rechecked = validate_no_symlink_chain(
                baseline_lexical,
                label="baseline output",
                leaf_may_be_missing=True,
            )
            current_identity = repository_identity(
                repo,
                max_git_seconds=args.max_git_seconds,
            )
            baseline_resolved_after = validate_outside_repository_storage(
                baseline_rechecked,
                repository_roots=(
                    Path(current_identity["worktree"]),
                    Path(current_identity["git_common_dir"]),
                ),
                label="baseline output",
            )
            if baseline_resolved_after != baseline_path:
                raise ValueError("baseline output target changed during capture")
        except (OSError, ValueError) as exc:
            raise SystemExit(f"baseline output changed during capture: {exc}") from exc
        write_new_baseline(
            baseline_path,
            baseline_payload(
                repo,
                snapshot=snapshot,
                tracked_patch=patch,
                extra_sensitive=args.sensitive_path,
                task=args.task,
                allow_dirty_baseline=bool(snapshot["changes"]),
                captured_git=captured_git,
                max_git_seconds=args.max_git_seconds,
            ),
        )
    print(json.dumps(assessment, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
