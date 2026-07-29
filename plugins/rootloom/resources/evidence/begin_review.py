#!/usr/bin/env python3
"""Create an intake-sealed Rootloom review directory."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

from runner.baseline import (
    baseline_payload,
    read_baseline_payload_with_hash,
    repository_identity,
    write_new_baseline,
)
from runner.evidence_paths import (
    fsync_directory,
    rename_directory_no_replace,
    validate_no_symlink_chain,
    validate_outside_repository_storage,
)
from runner.review_run import (
    CONTRACT_DRAFT_SENTINEL,
    REVIEW_MANIFEST_FORMAT,
    write_new_json,
)
from runner.state import (
    CaptureDeadline,
    DEFAULT_MAX_CAPTURE_SECONDS,
    DEFAULT_MAX_GIT_SECONDS,
    DEFAULT_MAX_SENSITIVE_PATHS,
    canonical_reviewable_paths,
    stable_repository_capture,
)
from rootloom_paths import (
    MAX_REVIEWABLE_PATHS,
    normalize_reviewable_paths,
    validate_reviewable_paths,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument(
        "--allow-all-paths",
        action="store_true",
        help="explicitly allow the entire repository when no --path is provided",
    )
    parser.add_argument(
        "--allow-dirty-baseline",
        action="store_true",
        help="explicitly capture pre-existing worktree/index changes",
    )
    parser.add_argument("--sensitive-path", action="append", default=[])
    parser.add_argument(
        "--reviewable-path",
        action="append",
        default=[],
        metavar="FILE",
        help=(
            "Intake-only exact-file reviewability declaration; the declaration "
            "is sealed, remains high risk, and cannot override "
            "strong or explicitly declared secrets"
        ),
    )
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
    try:
        output_lexical = validate_no_symlink_chain(
            args.output,
            label="review output",
            leaf_may_be_missing=True,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not (repo / ".git").exists():
        raise SystemExit(f"not a Git repository: {repo}")
    try:
        identity = repository_identity(
            repo,
            max_git_seconds=args.max_git_seconds,
        )
        output = validate_outside_repository_storage(
            output_lexical,
            repository_roots=(
                Path(identity["worktree"]),
                Path(identity["git_common_dir"]),
            ),
            label="review output",
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    if output.exists():
        raise SystemExit(f"review output already exists: {output}")
    if not args.path and not args.allow_all_paths:
        raise SystemExit("begin_review requires at least one --path or --allow-all-paths")
    if args.path and args.allow_all_paths:
        raise SystemExit("--allow-all-paths cannot be combined with --path")
    if not output.parent.is_dir():
        raise SystemExit(f"review output parent does not exist: {output.parent}")
    capture_deadline = CaptureDeadline(args.max_capture_seconds)
    try:
        requested_reviewable_paths = normalize_reviewable_paths(
            args.reviewable_path,
            extra_sensitive=set(args.sensitive_path),
            max_paths=MAX_REVIEWABLE_PATHS,
        )
        reviewable_paths = canonical_reviewable_paths(
            repo,
            requested_reviewable_paths,
            max_paths=MAX_REVIEWABLE_PATHS,
            max_git_seconds=args.max_git_seconds,
            capture_deadline=capture_deadline,
        )
        reviewable_paths = validate_reviewable_paths(
            repo,
            reviewable_paths,
            extra_sensitive=set(args.sensitive_path),
            max_paths=MAX_REVIEWABLE_PATHS,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    try:
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
            reviewable_paths=reviewable_paths,
            max_capture_seconds=args.max_capture_seconds,
            max_git_seconds=args.max_git_seconds,
            max_sensitive_paths=args.max_sensitive_paths,
            max_reviewable_paths=MAX_REVIEWABLE_PATHS,
            capture_deadline=capture_deadline,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    if snapshot["changes"] and not args.allow_dirty_baseline:
        raise SystemExit(
            "begin_review requires a clean worktree and index; "
            "use --allow-dirty-baseline to capture pre-existing changes"
        )
    baseline = baseline_payload(
        repo,
        snapshot=snapshot,
        tracked_patch=patch,
        extra_sensitive=args.sensitive_path,
        reviewable_paths=reviewable_paths,
        task=args.task,
        provenance="intake-sealed",
        allow_dirty_baseline=args.allow_dirty_baseline,
        captured_git=captured_git,
        max_git_seconds=args.max_git_seconds,
    )
    try:
        recaptured_reviewable_paths = canonical_reviewable_paths(
            repo,
            reviewable_paths,
            max_paths=MAX_REVIEWABLE_PATHS,
            max_git_seconds=args.max_git_seconds,
            capture_deadline=capture_deadline,
        )
        if recaptured_reviewable_paths != reviewable_paths or validate_reviewable_paths(
            repo,
            recaptured_reviewable_paths,
            extra_sensitive=set(args.sensitive_path),
            max_paths=MAX_REVIEWABLE_PATHS,
        ) != reviewable_paths:
            raise ValueError("reviewable path policy changed during capture")
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent)
    )
    try:
        os.chmod(temporary, 0o700)
        baseline_path = temporary / "baseline.json"
        write_new_baseline(baseline_path, baseline)
        persisted_baseline, baseline_file_sha256 = read_baseline_payload_with_hash(
            baseline_path
        )
        if persisted_baseline != baseline:
            raise ValueError("persisted baseline does not match captured baseline")
        command = CONTRACT_DRAFT_SENTINEL
        contract = {
            "format": "rootloom-change-contract-v1",
            "run_id": baseline["run_id"],
            "nonce": baseline["nonce"],
            "baseline_sha256": baseline_file_sha256,
            "task_sha256": baseline["task_sha256"],
            "allowed_paths": args.path or ["**"],
            "forbidden_paths": [],
            "root_cause_alignment": "NOT_APPLICABLE",
            "verification_commands": {"verify-primary": command},
            "verification_claims": {
                "primary-behavior": [
                    {
                        "id": "primary-behavior",
                        "command_ids": ["verify-primary"],
                        "target": CONTRACT_DRAFT_SENTINEL,
                        "expected_evidence": CONTRACT_DRAFT_SENTINEL,
                        "evidence_kind": "manual-review",
                    }
                ]
            },
        }
        write_new_json(temporary / "change-contract.draft.json", contract)
        manifest = {
            "format": REVIEW_MANIFEST_FORMAT,
            "run_id": baseline["run_id"],
            "baseline": "baseline.json",
            "baseline_sha256": contract["baseline_sha256"],
            "change_contract_draft": "change-contract.draft.json",
            "nonce": baseline["nonce"],
            "task_sha256": baseline["task_sha256"],
            "next_step": (
                "Replace every Rootloom contract placeholder, edit "
                "change-contract.draft.json, then run seal_contract.py "
                "--review-dir this-directory. Use --recover only to validate "
                "and finish an exact interrupted seal publication."
            ),
        }
        write_new_json(temporary / "review.json", manifest)
        fsync_directory(temporary)
        output_rechecked = validate_no_symlink_chain(
            output_lexical,
            label="review output",
            leaf_may_be_missing=True,
        )
        current_identity = repository_identity(
            repo,
            max_git_seconds=args.max_git_seconds,
        )
        output_resolved_after = validate_outside_repository_storage(
            output_rechecked,
            repository_roots=(
                Path(current_identity["worktree"]),
                Path(current_identity["git_common_dir"]),
            ),
            label="review output",
        )
        if output_resolved_after != output:
            raise ValueError("review output target changed during capture")
        rename_directory_no_replace(temporary, output)
        fsync_directory(output.parent)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    print(json.dumps(manifest, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
