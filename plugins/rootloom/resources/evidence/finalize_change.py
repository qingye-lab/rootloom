#!/usr/bin/env python3
"""Verify a personal engineering change and write a bounded review bundle."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any


PLUGIN_LIB = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(PLUGIN_LIB))
from rootloom_paths import (
    MAX_REVIEWABLE_PATHS,
    is_protected_deletion_path,
    normalize_repo_path,
    normalize_reviewable_paths,
)

from runner.baseline import (
    BASELINE_FORMAT_V2,
    BASELINE_FORMAT_V3,
    BASELINE_FORMAT_V4,
    read_baseline_with_hash,
    repository_identity,
    sensitive_preservation,
    task_sha256,
)
from runner.change_contract import (
    claimed_commands,
    load_change_contract,
    parse_cli_claim,
    scope_violations,
    structured_contract_claimed_commands,
    verification_coverage,
)
from runner.contracts import (
    DANGEROUS_DELETE_EXIT,
    REINTAKE_REQUIRED_EXIT,
    RISK_LEVELS,
    SUMMARY_FORMAT,
    SUMMARY_SCHEMA_REVISION,
)
from runner.errors import DangerousDeletionError
from runner.evidence_paths import (
    validate_no_symlink_chain,
    validate_outside_repository_storage,
)
from runner.intelligence import analyze_change
from runner.review_run import (
    read_json_no_follow,
    validate_contract_seal,
    validate_review_manifest,
)
from runner.state import (
    CaptureDeadline,
    DEFAULT_MAX_CAPTURE_SECONDS,
    DEFAULT_MAX_GIT_SECONDS,
    DEFAULT_MAX_SENSITIVE_PATHS,
    discover_sensitive_paths,
    filter_untracked_patch,
    git_identity,
    metadata_only,
    snapshot_identity,
    stable_repository_capture,
)
from runner.verification import split_command, verify


DEFAULT_MAX_PATCH_BYTES = 16 * 1024 * 1024
MAX_VERIFY_COMMANDS = 20
MAX_COMMAND_CHARS = 8192
MAX_REMAINING_RISKS = 20
MAX_REMAINING_RISK_CHARS = 4096
QUALITY_EXIT_CODES = {
    "REVIEW_EVIDENCE_COMPLETE": 0,
    "REVIEW_REQUIRED_WITH_REDACTIONS": 4,
    "SEMANTIC_REVIEW_ASSERTED": 4,
    "MECHANICALLY_VERIFIED": 4,
    "COMMANDS_PASSED": 4,
    "NO_CHANGE": 3,
    "UNVERIFIED": 4,
    "FAILED": 1,
}


def is_intake_sealed_baseline(baseline: dict[str, Any]) -> bool:
    return baseline.get("evidence_provenance") == {
        BASELINE_FORMAT_V2: "operator-sealed",
        BASELINE_FORMAT_V3: "intake-sealed",
        BASELINE_FORMAT_V4: "intake-sealed",
    }.get(baseline.get("format"))


BUNDLE_MARKER = ".rootloom-engineering-bundle.json"
BUNDLE_MARKER_FORMAT = "rootloom-engineering-bundle-owner-v1"
BUNDLE_FILES = {BUNDLE_MARKER, "diff.patch", "test.log", "summary.json"}
MAX_BUNDLE_DIRECTORY_ENTRIES = len(BUNDLE_FILES) + 1
REVIEW_MANIFEST = "review.json"
CONTRACT_SEAL = "contract.seal.json"


def load_review_run(
    baseline_path: Path,
    contract_path: Path | None,
    *,
    baseline: dict[str, Any],
    baseline_sha256: str | None,
    contract: dict[str, Any] | None,
) -> tuple[bool, dict[str, Any]]:
    detail: dict[str, Any] = {
        "provided": False,
        "path": None,
        "contract_seal_path": None,
        "valid": False,
        "errors": [],
    }
    if contract_path is None or baseline_path.parent != contract_path.parent:
        detail["errors"].append("baseline and change contract are not in one review run directory")
        return False, detail
    if baseline_path.name != "baseline.json" or contract_path.name != "change-contract.json":
        detail["errors"].append("review run uses unexpected baseline or contract filename")
        return False, detail
    manifest_path = baseline_path.parent / REVIEW_MANIFEST
    seal_path = baseline_path.parent / CONTRACT_SEAL
    detail["path"] = str(manifest_path)
    detail["contract_seal_path"] = str(seal_path)
    try:
        payload, manifest_raw = read_json_no_follow(
            manifest_path, label="review manifest"
        )
        validate_review_manifest(
            payload,
            baseline_name=baseline_path.name,
            baseline_sha256=baseline_sha256 or "",
            baseline=baseline,
        )
        seal, seal_raw = read_json_no_follow(seal_path, label="contract seal")
        validate_contract_seal(
            seal,
            baseline=baseline,
            baseline_sha256=baseline_sha256 or "",
            review_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
            contract_sha256=contract.get("actual_contract_sha256") if contract else "",
            contract_file_sha256=(
                contract.get("actual_contract_file_sha256") if contract else ""
            ),
        )
    except FileNotFoundError:
        detail["errors"].append("review manifest or contract seal is missing")
        return False, detail
    except (OSError, ValueError) as exc:
        detail["errors"].append(f"review run is invalid: {exc}")
        return False, detail
    detail["provided"] = True
    detail["valid"] = True
    detail["contract_sha256"] = contract.get("actual_contract_sha256") if contract else None
    detail["manifest_file_sha256"] = hashlib.sha256(manifest_raw).hexdigest()
    detail["contract_seal_file_sha256"] = hashlib.sha256(seal_raw).hexdigest()
    return True, detail


def validated_external_evidence_path(
    path: Path,
    *,
    repo: Path,
    label: str,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
) -> Path:
    lexical = validate_no_symlink_chain(
        path,
        label=label,
        leaf_may_be_missing=False,
    )
    identity = repository_identity(repo, max_git_seconds=max_git_seconds)
    validate_outside_repository_storage(
        lexical,
        repository_roots=(
            Path(identity["worktree"]),
            Path(identity["git_common_dir"]),
        ),
        label=label,
    )
    return lexical


def revalidate_evidence_inputs(
    repo: Path,
    *,
    baseline_path: Path | None,
    baseline: dict[str, Any] | None,
    baseline_sha256: str | None,
    contract_path: Path | None,
    contract: dict[str, Any] | None,
    review_detail: dict[str, Any],
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    expected_review_detail = review_detail
    observed_baseline = baseline
    observed_baseline_sha256 = baseline_sha256
    observed_contract = contract
    try:
        if baseline_path is not None:
            baseline_path = validated_external_evidence_path(
                baseline_path,
                repo=repo,
                label="baseline path",
                max_git_seconds=max_git_seconds,
            )
            observed_baseline, observed_baseline_sha256 = read_baseline_with_hash(
                baseline_path,
                repo,
                max_git_seconds=max_git_seconds,
            )
            if observed_baseline_sha256 != baseline_sha256:
                errors.append("baseline bytes changed during verification")
        if contract_path is not None:
            contract_path = validated_external_evidence_path(
                contract_path,
                repo=repo,
                label="change contract path",
                max_git_seconds=max_git_seconds,
            )
            observed_contract = load_change_contract(contract_path)
            if contract is None or (
                observed_contract["actual_contract_file_sha256"]
                != contract.get("actual_contract_file_sha256")
            ):
                errors.append("change contract bytes changed during verification")
        if review_detail.get("valid") and baseline_path is not None:
            review_valid, observed_review_detail = load_review_run(
                baseline_path,
                contract_path,
                baseline=observed_baseline or {},
                baseline_sha256=observed_baseline_sha256,
                contract=observed_contract,
            )
            if not review_valid:
                errors.extend(
                    f"review evidence changed during verification: {item}"
                    for item in observed_review_detail["errors"]
                )
            else:
                for field, label in (
                    ("manifest_file_sha256", "review manifest bytes"),
                    ("contract_seal_file_sha256", "contract seal bytes"),
                ):
                    if observed_review_detail.get(field) != expected_review_detail.get(
                        field
                    ):
                        errors.append(f"{label} changed during verification")
    except (OSError, ValueError) as exc:
        errors.append(f"evidence input changed during verification: {exc}")
    return not errors, list(dict.fromkeys(errors))


def dangerous_deletions(
    changes: list[dict[str, str]],
    *,
    extra_sensitive: set[str] | None = None,
    reviewable_paths: set[str] | None = None,
) -> list[str]:
    dangerous: set[str] = set()
    for item in changes:
        if "D" in item["status"] and is_protected_deletion_path(
            item["path"],
            extra_sensitive=extra_sensitive,
            reviewable_paths=reviewable_paths,
        ):
            dangerous.add(item["path"])
        if (
            "R" in item["status"]
            and item["original_path"]
            and is_protected_deletion_path(
                item["original_path"],
                extra_sensitive=extra_sensitive,
                reviewable_paths=reviewable_paths,
            )
        ):
            dangerous.add(item["original_path"])
    return sorted(dangerous)


def sensitive_path_changes(
    repo: Path,
    snapshot: dict[str, Any],
    *,
    extra_sensitive: set[str],
    reviewable_paths: set[str] | None = None,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    max_sensitive_paths: int = DEFAULT_MAX_SENSITIVE_PATHS,
    capture_deadline: CaptureDeadline | None = None,
) -> dict[str, list[str]]:
    """Compare known sensitive metadata before any changed content is read."""

    before: dict[str, dict[str, Any]] = {}
    for item in snapshot.get("sensitive_paths", []):
        if capture_deadline is not None:
            capture_deadline.checkpoint()
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        before[item["path"]] = item
    current_paths = set(
        discover_sensitive_paths(
            repo,
            extra_sensitive,
            reviewable_paths=reviewable_paths,
            max_git_seconds=max_git_seconds,
            max_sensitive_paths=max_sensitive_paths,
            capture_deadline=capture_deadline,
        )
    ) | set(before)
    if len(current_paths) > max_sensitive_paths:
        raise ValueError(
            "sensitive preflight exceeds configured "
            f"{max_sensitive_paths}-path budget"
        )
    after = {
        path: metadata_only(repo, path, capture_deadline=capture_deadline)
        for path in sorted(current_paths)
    }
    changed = sorted(
        path
        for path, metadata in before.items()
        if metadata.get("exists")
        and after[path].get("exists")
        and metadata != after[path]
    )
    missing = sorted(
        path
        for path, metadata in before.items()
        if metadata.get("exists") and not after[path].get("exists")
    )
    added = sorted(
        path
        for path, metadata in after.items()
        if metadata.get("exists") and not before.get(path, {}).get("exists")
    )
    if capture_deadline is not None:
        capture_deadline.checkpoint()
    return {"changed": changed, "missing": missing, "added": added}


def captured_changes(
    snapshot: dict[str, Any], baseline_guard: dict[str, list[str] | bool]
) -> list[dict[str, str]]:
    """Combine Git status with metadata-only sensitive changes."""

    git_change_paths = {
        item.get(field)
        for item in snapshot["changes"]
        for field in ("path", "original_path")
        if item.get(field)
    }
    sensitive_task_changes = [
        {"status": status, "path": path, "original_path": ""}
        for status, paths in (
            ("??", baseline_guard["added"]),
            (" M", baseline_guard["changed"]),
            (" D", baseline_guard["missing"]),
        )
        for path in paths
        if path not in git_change_paths
    ]
    return [*snapshot["changes"], *sensitive_task_changes]


def partition_task_changes(
    *,
    baseline: dict[str, Any] | None,
    snapshot: dict[str, Any],
    tracked_patch: bytes,
    current_changes: list[dict[str, str]],
    baseline_guard: dict[str, list[str] | bool],
) -> dict[str, Any]:
    """Attribute captured state to the task without claiming ambiguous precision."""

    preexisting_changes = (
        list(baseline.get("preexisting_changes", [])) if baseline is not None else []
    )
    preexisting_keys = {
        (item.get("status"), item.get("path"), item.get("original_path"))
        for item in preexisting_changes
        if isinstance(item, dict)
    }
    preexisting_paths = {
        item.get(field)
        for item in preexisting_changes
        if isinstance(item, dict)
        for field in ("path", "original_path")
        if item.get(field)
    }
    current_paths = {
        item.get(field)
        for item in current_changes
        for field in ("path", "original_path")
        if item.get(field)
    }
    removed_preexisting_paths = sorted(preexisting_paths - current_paths)
    task_changes = [
        item
        for item in current_changes
        if (item.get("status"), item.get("path"), item.get("original_path"))
        not in preexisting_keys
    ]
    tracked_patch_changed = baseline is None or (
        hashlib.sha256(tracked_patch).hexdigest()
        != baseline.get("tracked_patch_sha256")
    )
    baseline_state_changed = baseline is None or (
        snapshot != baseline.get("snapshot") or tracked_patch_changed
    )
    change_partition = "no-baseline" if baseline is None else "exact"
    if (
        baseline is not None
        and baseline_state_changed
        and preexisting_changes
        and current_changes
    ):
        # Baseline v2 stores one aggregate tracked-patch hash, so changed tracked
        # patches keep every overlapping tracked endpoint conservative. Untracked
        # entries have per-path fingerprints and can remain exactly pre-existing.
        overlap_paths = set(baseline_guard["changed"])
        if tracked_patch_changed:
            overlap_paths.update(
                item.get(field)
                for item in preexisting_changes
                if isinstance(item, dict) and item.get("status") != "??"
                for field in ("path", "original_path")
                if item.get(field) in current_paths
            )
        baseline_untracked = {
            item["path"]: item
            for item in baseline.get("snapshot", {}).get("untracked", [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        current_untracked = {
            item["path"]: item
            for item in snapshot.get("untracked", [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        for item in preexisting_changes:
            if not isinstance(item, dict) or item.get("status") != "??":
                continue
            path = item.get("path")
            if (
                isinstance(path, str)
                and path in current_paths
                and baseline_untracked.get(path) != current_untracked.get(path)
            ):
                overlap_paths.add(path)
        if overlap_paths:
            task_changes = [
                item
                for item in current_changes
                if (
                    item.get("status"),
                    item.get("path"),
                    item.get("original_path"),
                )
                not in preexisting_keys
                or any(
                    item.get(field) in overlap_paths
                    for field in ("path", "original_path")
                )
            ]
            change_partition = "conservative-overlap"
    if removed_preexisting_paths:
        change_partition = "preexisting-state-removed"
    return {
        "preexisting_changes": preexisting_changes,
        "removed_preexisting_paths": removed_preexisting_paths,
        "task_changes": task_changes,
        "change_partition": change_partition,
        "tracked_patch_changed": tracked_patch_changed,
    }


def task_evidence_patch(
    *,
    baseline: dict[str, Any] | None,
    tracked_patch: bytes,
    untracked_patch: bytes,
    task_changes: list[dict[str, str]],
) -> bytes:
    """Build the patch from the same task partition used for scope and risk."""

    tracked_patch_changed = baseline is None or (
        hashlib.sha256(tracked_patch).hexdigest()
        != baseline.get("tracked_patch_sha256")
    )
    task_tracked_patch = tracked_patch if tracked_patch_changed else b""
    task_untracked_paths = {
        item["path"]
        for item in task_changes
        if item.get("status") == "??" and item.get("path")
    }
    task_untracked_patch = filter_untracked_patch(
        untracked_patch, task_untracked_paths
    )
    return task_tracked_patch + (
        b"\n" if task_tracked_patch and task_untracked_patch else b""
    ) + task_untracked_patch


def atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def output_preflight(output: Path) -> None:
    if output.is_symlink():
        raise ValueError("output directory must not be a symlink")
    if not output.exists():
        return
    if not output.is_dir():
        raise ValueError("output path must be a directory")
    entries: set[str] = set()
    for item in output.iterdir():
        entries.add(item.name)
        if len(entries) > MAX_BUNDLE_DIRECTORY_ENTRIES:
            raise ValueError("Rootloom output directory exceeds the entry limit")
    if not entries:
        return
    marker = output / BUNDLE_MARKER
    try:
        payload, _marker_raw = read_json_no_follow(
            marker, label="bundle ownership marker"
        )
    except (FileNotFoundError, OSError, ValueError):
        raise ValueError(
            "nonempty output directory requires a valid Rootloom ownership marker"
        ) from None
    if payload != {"format": BUNDLE_MARKER_FORMAT, "managed_by": "rootloom"}:
        raise ValueError("output directory has an invalid Rootloom ownership marker")
    unexpected = sorted(entries - BUNDLE_FILES)
    if unexpected:
        raise ValueError(
            "Rootloom-owned output directory contains unexpected files: "
            + ", ".join(unexpected)
        )


def invalidate_previous_summary(output: Path) -> None:
    """Prevent an early failure from leaving an authoritative stale result."""

    if not output.exists():
        return
    summary = output / "summary.json"
    try:
        info = summary.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISDIR(info.st_mode):
        raise ValueError("existing bundle summary path must not be a directory")
    summary.unlink()


def write_bundle(output: Path, *, patch: bytes, log: bytes, summary: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    marker = (
        json.dumps(
            {"format": BUNDLE_MARKER_FORMAT, "managed_by": "rootloom"},
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    atomic_write(output / BUNDLE_MARKER, marker)
    atomic_write(output / "diff.patch", patch)
    atomic_write(output / "test.log", log)
    atomic_write(
        output / "summary.json",
        (
            json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        ).encode("ascii"),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--task", default="")
    parser.add_argument("--risk", choices=RISK_LEVELS)
    parser.add_argument("--verify", action="append", default=[])
    parser.add_argument("--verify-claim", action="append", default=[])
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--change-contract", type=Path)
    parser.add_argument("--sensitive-path", action="append", default=[])
    parser.add_argument("--remaining-risk", action="append", default=[])
    parser.add_argument("--confirm-dangerous-delete", action="append", default=[])
    parser.add_argument("--allow-no-change", action="store_true")
    parser.add_argument("--exit-policy", choices=("bundle", "quality"))
    parser.add_argument(
        "--require-verified",
        action="store_true",
        help="CI-friendly alias for --exit-policy quality",
    )
    parser.add_argument(
        "--semantic-coverage",
        choices=("unknown", "partial", "reviewed"),
        default="unknown",
    )
    parser.add_argument("--max-baseline-age-seconds", type=int)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="require governed Tier 1/2 evidence and fail on incomplete coverage",
    )
    parser.add_argument(
        "--strict-bundle-only",
        action="store_true",
        help="run strict evidence gates but return bundle-style status codes",
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-output-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--max-patch-bytes", type=int, default=DEFAULT_MAX_PATCH_BYTES)
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
    if args.strict_bundle_only and not args.strict:
        raise SystemExit("--strict-bundle-only requires --strict")
    if args.strict_bundle_only and args.require_verified:
        raise SystemExit("--strict-bundle-only cannot be combined with --require-verified")
    if args.strict_bundle_only and args.exit_policy == "quality":
        raise SystemExit("--strict-bundle-only cannot use --exit-policy quality")
    if args.strict and args.exit_policy == "bundle" and not args.strict_bundle_only:
        raise SystemExit("use --strict-bundle-only for non-blocking strict bundle output")
    if args.strict_bundle_only:
        args.exit_policy = "bundle"
    elif args.strict or args.require_verified:
        args.exit_policy = "quality"
    elif args.exit_policy is None:
        args.exit_policy = "bundle"
    repo = args.repo.expanduser().resolve()
    try:
        output_lexical = validate_no_symlink_chain(
            args.output,
            label="output directory",
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
            label="output directory",
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    if args.timeout <= 0 or args.max_output_bytes <= 0 or args.max_patch_bytes <= 0:
        raise SystemExit("timeout, output budget, and patch budget must be positive")
    if args.max_baseline_age_seconds is not None and args.max_baseline_age_seconds < 0:
        raise SystemExit("max baseline age must be nonnegative")
    try:
        output_preflight(output)
        invalidate_previous_summary(output)
        cli_claims = [parse_cli_claim(value) for value in args.verify_claim]
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    commands = list(args.verify)
    for _claim, command in cli_claims:
        if command not in commands:
            commands.append(command)
    if len(commands) > MAX_VERIFY_COMMANDS:
        raise SystemExit(f"at most {MAX_VERIFY_COMMANDS} verification commands are supported")
    if any(len(command) > MAX_COMMAND_CHARS for command in commands):
        raise SystemExit(f"verification commands must be at most {MAX_COMMAND_CHARS} characters")
    try:
        for command in commands:
            split_command(command)
    except ValueError as exc:
        raise SystemExit(f"invalid verification command: {exc}") from exc
    if len(args.remaining_risk) > MAX_REMAINING_RISKS or any(
        len(value) > MAX_REMAINING_RISK_CHARS for value in args.remaining_risk
    ):
        raise SystemExit(
            f"at most {MAX_REMAINING_RISKS} remaining risks of "
            f"{MAX_REMAINING_RISK_CHARS} characters are supported"
        )

    baseline: dict[str, Any] | None = None
    baseline_path: Path | None = None
    baseline_sha256: str | None = None
    baseline_extra: list[str] = []
    baseline_reviewable: list[str] = []
    baseline_missing_reviewable: set[str] = set()
    if args.baseline:
        try:
            baseline_path = validated_external_evidence_path(
                args.baseline,
                repo=repo,
                label="baseline path",
                max_git_seconds=args.max_git_seconds,
            )
            baseline, baseline_sha256 = read_baseline_with_hash(
                baseline_path,
                repo,
                max_git_seconds=args.max_git_seconds,
            )
            baseline_extra = list(baseline["sensitive_paths"])
            baseline_reviewable = list(baseline.get("reviewable_paths", []))
            try:
                current_reviewable = normalize_reviewable_paths(
                    baseline_reviewable,
                    extra_sensitive=set(baseline_extra),
                    max_paths=MAX_REVIEWABLE_PATHS,
                )
                if current_reviewable != baseline_reviewable:
                    raise ValueError(
                        "reviewable paths do not match current canonical policy"
                    )
            except ValueError as exc:
                print(
                    json.dumps(
                        {
                            "status": "reintake-required",
                            "reason": str(exc),
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                    )
                )
                return REINTAKE_REQUIRED_EXIT
            baseline_reviewable_set = set(baseline_reviewable)
            baseline_missing_reviewable = {
                item["path"]
                for item in baseline["snapshot"]["untracked"]
                if isinstance(item, dict)
                and item.get("path") in baseline_reviewable_set
                and item.get("kind") == "file"
                and item.get("exists") is True
                and item.get("sensitive") is False
                and item.get("content_read") is True
            }
        except (OSError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
    normalized_cli_sensitive = sorted(
        {
            normalize_repo_path(path, label="sensitive path")
            for path in args.sensitive_path
        }
    )
    if args.strict and baseline is not None:
        baseline_sensitive_keys = {
            path.casefold()
            for path in [
                *baseline_extra,
                *[
                    item["path"]
                    for item in baseline["snapshot"]["sensitive_paths"]
                    if isinstance(item, dict) and isinstance(item.get("path"), str)
                ],
            ]
        }
        undeclared_sensitive = sorted(
            path
            for path in normalized_cli_sensitive
            if path.casefold() not in baseline_sensitive_keys
        )
        if undeclared_sensitive:
            raise SystemExit(
                "strict sensitive paths must be declared in the baseline intake: "
                + ", ".join(undeclared_sensitive)
            )
    extra_sensitive = sorted(
        {
            normalize_repo_path(path, label="sensitive path")
            for path in [*normalized_cli_sensitive, *baseline_extra]
        }
    )
    confirmed = sorted(
        {
            normalize_repo_path(path, label="dangerous deletion confirmation")
            for path in args.confirm_dangerous_delete
        }
    )
    baseline_sensitive_preflight = {"changed": [], "missing": [], "added": []}
    capture_deadline_before = CaptureDeadline(args.max_capture_seconds)
    if baseline is not None:
        try:
            baseline_sensitive_preflight = sensitive_path_changes(
                repo,
                baseline["snapshot"],
                extra_sensitive=set(extra_sensitive),
                reviewable_paths=set(baseline_reviewable),
                max_git_seconds=args.max_git_seconds,
                max_sensitive_paths=args.max_sensitive_paths,
                capture_deadline=capture_deadline_before,
            )
        except (OSError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
    unconfirmed_baseline_missing = sorted(
        set(baseline_sensitive_preflight["missing"]) - set(confirmed)
    )
    if unconfirmed_baseline_missing:
        error = DangerousDeletionError(
            "dangerous deletions require exact confirmation: "
            + ", ".join(unconfirmed_baseline_missing)
        )
        print(str(error))
        return DANGEROUS_DELETE_EXIT
    sensitive_deletion_quarantine = bool(baseline_sensitive_preflight["missing"])
    sensitive_change_quarantine = bool(
        baseline_sensitive_preflight["changed"]
        or baseline_sensitive_preflight["missing"]
        or baseline_sensitive_preflight["added"]
    )
    try:
        (
            snapshot_before,
            untracked_patch_before,
            patch_before,
            current_git,
            capture_duration_before,
            reviewable_metadata_before,
        ) = stable_repository_capture(
            repo,
            extra_sensitive=extra_sensitive,
            reviewable_paths=baseline_reviewable,
            allowed_missing_reviewable_paths=baseline_missing_reviewable,
            reference_sensitive_metadata=(
                baseline["snapshot"]["sensitive_paths"]
                if baseline is not None
                else None
            ),
            max_patch_bytes=args.max_patch_bytes,
            protect_changed_paths=sensitive_change_quarantine,
            max_capture_seconds=args.max_capture_seconds,
            max_git_seconds=args.max_git_seconds,
            max_sensitive_paths=args.max_sensitive_paths,
            max_reviewable_paths=MAX_REVIEWABLE_PATHS,
            capture_deadline=capture_deadline_before,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    capture_sensitive_change_quarantine = bool(
        snapshot_before["bounds"].get("sensitive_change_quarantine")
    )
    baseline_guard = (
        sensitive_preservation(baseline, snapshot_before)
        if baseline is not None
        else {"preserved": True, "missing": [], "changed": [], "added": []}
    )
    current_changes = captured_changes(snapshot_before, baseline_guard)
    partition = partition_task_changes(
        baseline=baseline,
        snapshot=snapshot_before,
        tracked_patch=patch_before,
        current_changes=current_changes,
        baseline_guard=baseline_guard,
    )
    preexisting_changes = partition["preexisting_changes"]
    removed_preexisting_paths = partition["removed_preexisting_paths"]
    task_changes = partition["task_changes"]
    change_partition = partition["change_partition"]
    analysis_patch = task_evidence_patch(
        baseline=baseline,
        tracked_patch=patch_before,
        untracked_patch=untracked_patch_before,
        task_changes=task_changes,
    )
    assessment = analyze_change(
        repo,
        task=args.task,
        anticipated_paths=[],
        changes=task_changes,
        tracked_patch=analysis_patch,
        declared_risk=args.risk,
        reviewable_paths=baseline_reviewable,
        allow_repository_reads=not bool(
            snapshot_before["bounds"].get("sensitive_change_quarantine")
        ),
    )
    tier = int(assessment["minimum_tier"])
    if args.strict and tier >= 1 and baseline is None:
        raise SystemExit("Tier 1/2 finalization requires --baseline from pre-change analysis")
    if args.strict and tier >= 1 and args.change_contract is None:
        raise SystemExit("Tier 1/2 finalization requires --change-contract")

    contract: dict[str, Any] | None = None
    contract_path: Path | None = None
    contract_sha256: str | None = None
    if args.change_contract:
        try:
            contract_path = validated_external_evidence_path(
                args.change_contract,
                repo=repo,
                label="change contract path",
                max_git_seconds=args.max_git_seconds,
            )
            contract = load_change_contract(contract_path)
            contract_sha256 = contract["actual_contract_sha256"]
        except (OSError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
    scope = (
        scope_violations(contract, task_changes)
        if contract is not None
        else {"outside_allowed_paths": [], "forbidden_paths_changed": []}
    )
    contract_scope_valid = not any(scope.values())
    defect_repair = "defect-repair" in {
        item["id"] for item in assessment["signals"]
    }
    root_cause_alignment = (
        contract.get("root_cause_alignment") if contract is not None else None
    )
    root_cause_valid = not defect_repair or root_cause_alignment == "PASS"
    expected_task_sha256 = task_sha256(args.task)
    baseline_age_seconds: int | None = None
    baseline_freshness = "not-provided"
    baseline_intake_sealed = False
    contract_workflow_sealed = False
    review_manifest: dict[str, Any] = {"provided": False, "valid": False, "errors": []}
    hash_chain_errors: list[str] = []
    if baseline is not None:
        created_at = baseline.get("created_at")
        if isinstance(created_at, str):
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                baseline_age_seconds = int(
                    (datetime.now(UTC) - created.astimezone(UTC)).total_seconds()
                )
                baseline_freshness = (
                    "future-clock-skew" if baseline_age_seconds < 0 else "fresh"
                )
                if (
                    args.max_baseline_age_seconds is not None
                    and baseline_age_seconds > args.max_baseline_age_seconds
                ):
                    baseline_freshness = "too-old"
                    hash_chain_errors.append("baseline exceeds max age")
                elif baseline_age_seconds > 24 * 60 * 60:
                    baseline_freshness = "old"
            except ValueError:
                baseline_freshness = "unknown"
        if baseline.get("task_sha256") not in {None, expected_task_sha256}:
            hash_chain_errors.append("baseline task_sha256 does not match task")
        if args.strict and baseline.get("format") in {
            BASELINE_FORMAT_V2,
            BASELINE_FORMAT_V3,
            BASELINE_FORMAT_V4,
        }:
            baseline_git = baseline.get("git", {})
            if baseline_git.get("head") != current_git.get("head"):
                hash_chain_errors.append("repository HEAD changed since baseline")
            if baseline_git.get("head_ref") != current_git.get("head_ref"):
                hash_chain_errors.append("repository HEAD ref changed since baseline")
            if baseline_git.get("index_sha256") != current_git.get("index_sha256"):
                hash_chain_errors.append("repository index changed since baseline")
        if contract is not None:
            if contract.get("baseline_sha256") != baseline_sha256:
                hash_chain_errors.append("change contract baseline_sha256 does not match baseline")
            for field in ("task_sha256", "run_id", "nonce"):
                baseline_value = expected_task_sha256 if field == "task_sha256" else baseline.get(field)
                contract_value = contract.get(field)
                if contract_value != baseline_value:
                    hash_chain_errors.append(f"change contract {field} does not match baseline")
            review_run_valid, review_manifest = load_review_run(
                baseline_path,
                contract_path,
                baseline=baseline,
                baseline_sha256=baseline_sha256,
                contract=contract,
            )
            baseline_intake_sealed = (
                is_intake_sealed_baseline(baseline) and review_run_valid
            )
            contract_workflow_sealed = (
                baseline_intake_sealed
                and bool(contract.get("declared_contract_sha256_valid"))
                and not hash_chain_errors
            )
            if (
                args.strict
                and is_intake_sealed_baseline(baseline)
                and not review_run_valid
            ):
                hash_chain_errors.extend(review_manifest["errors"])
    if args.strict and contract is not None and not contract.get(
        "declared_contract_sha256_valid"
    ):
        hash_chain_errors.append("change contract contract_sha256 is required in strict mode")
    if contract is not None and contract.get("task_sha256") not in {None, expected_task_sha256}:
        hash_chain_errors.append("change contract task_sha256 does not match task")
    hash_chain_errors = list(dict.fromkeys(hash_chain_errors))

    dangerous = set(
        dangerous_deletions(
            snapshot_before["changes"],
            extra_sensitive=set(extra_sensitive),
            reviewable_paths=set(baseline_reviewable),
        )
    )
    dangerous.update(baseline_guard["missing"])
    missing = sorted(dangerous - set(confirmed))
    if missing:
        error = DangerousDeletionError(
            "dangerous deletions require exact confirmation: " + ", ".join(missing)
        )
        print(str(error))
        return DANGEROUS_DELETE_EXIT

    changed_files = sorted(
        {
            item[field]
            for item in task_changes
            for field in ("path", "original_path")
            if item.get(field)
        }
    )
    has_change = bool(changed_files)
    gate_errors: list[str] = []
    if not contract_scope_valid:
        gate_errors.append("change contract path scope was violated")
    if args.strict and hash_chain_errors:
        gate_errors.extend(hash_chain_errors)
    if contract is not None and not root_cause_valid:
        gate_errors.append("behavioral defect requires ROOT_CAUSE_ALIGNMENT: PASS")
    if baseline_guard["changed"]:
        gate_errors.append("sensitive metadata changed since the pre-change baseline")
    if removed_preexisting_paths:
        gate_errors.append(
            "pre-existing dirty paths disappeared since the baseline: "
            + ", ".join(removed_preexisting_paths)
        )
    if not has_change and not args.allow_no_change:
        gate_errors.append("no repository change; use --allow-no-change for pure verification")
    if gate_errors:
        results = []
        log = ("Rootloom: " + "; ".join(gate_errors) + "\n").encode("utf-8")
    else:
        results, log = verify(
            commands,
            repo=repo,
            timeout=args.timeout,
            max_output_bytes=args.max_output_bytes,
        )

    capture_deadline_after = CaptureDeadline(args.max_capture_seconds)
    try:
        verification_sensitive_preflight = sensitive_path_changes(
            repo,
            snapshot_before,
            extra_sensitive=set(extra_sensitive),
            reviewable_paths=set(baseline_reviewable),
            max_git_seconds=args.max_git_seconds,
            max_sensitive_paths=args.max_sensitive_paths,
            capture_deadline=capture_deadline_after,
        )
        verification_sensitive_deletion_quarantine = bool(
            verification_sensitive_preflight["missing"]
        )
        verification_sensitive_change_quarantine = bool(
            verification_sensitive_preflight["changed"]
            or verification_sensitive_preflight["missing"]
            or verification_sensitive_preflight["added"]
        )
        (
            snapshot_after,
            untracked_patch_after,
            patch_after,
            current_git_after,
            capture_duration_after,
            reviewable_metadata_after,
        ) = stable_repository_capture(
            repo,
            extra_sensitive=extra_sensitive,
            reviewable_paths=baseline_reviewable,
            allowed_missing_reviewable_paths=baseline_missing_reviewable,
            reference_sensitive_metadata=snapshot_before["sensitive_paths"],
            max_patch_bytes=args.max_patch_bytes,
            protect_changed_paths=(
                capture_sensitive_change_quarantine
                or verification_sensitive_change_quarantine
            ),
            max_capture_seconds=args.max_capture_seconds,
            max_git_seconds=args.max_git_seconds,
            max_sensitive_paths=args.max_sensitive_paths,
            max_reviewable_paths=MAX_REVIEWABLE_PATHS,
            capture_deadline=capture_deadline_after,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    verification_capture_sensitive_change_quarantine = bool(
        snapshot_after["bounds"].get("sensitive_change_quarantine")
    )
    capture_preserved = (
        snapshot_after == snapshot_before
        and untracked_patch_after == untracked_patch_before
        and patch_after == patch_before
        and reviewable_metadata_after == reviewable_metadata_before
    )
    if not capture_preserved:
        log += (
            b"\nRootloom: verification changed the tracked patch or captured path/content set; "
            b"quality status is FAILED.\n"
        )
    post_execution_errors: list[str] = []
    repository_base_preserved = current_git_after == current_git
    if not repository_base_preserved:
        labels = {
            "head": "HEAD",
            "head_ref": "HEAD ref",
            "index_sha256": "index",
        }
        for field, label in labels.items():
            if current_git_after.get(field) != current_git.get(field):
                post_execution_errors.append(
                    f"repository {label} changed during verification"
                )
    evidence_files_preserved, evidence_preservation_errors = (
        revalidate_evidence_inputs(
            repo,
            baseline_path=baseline_path,
            baseline=baseline,
            baseline_sha256=baseline_sha256,
            contract_path=contract_path,
            contract=contract,
            review_detail=review_manifest,
            max_git_seconds=args.max_git_seconds,
        )
    )
    post_execution_errors.extend(evidence_preservation_errors)
    if not evidence_files_preserved:
        baseline_intake_sealed = False
        contract_workflow_sealed = False
    if post_execution_errors:
        hash_chain_errors.extend(post_execution_errors)
        hash_chain_errors = list(dict.fromkeys(hash_chain_errors))
        log += (
            "\nRootloom: post-verification trust inputs changed: "
            + "; ".join(post_execution_errors)
            + "; quality status is FAILED.\n"
        ).encode("utf-8")
    verification_sensitive = sensitive_preservation(
        {"snapshot": snapshot_before}, snapshot_after
    )
    dangerous_after = set(
        dangerous_deletions(
            snapshot_after["changes"],
            extra_sensitive=set(extra_sensitive),
            reviewable_paths=set(baseline_reviewable),
        )
    )
    dangerous_after.update(verification_sensitive["missing"])
    missing_after = sorted(dangerous_after - set(confirmed))
    if missing_after:
        error = DangerousDeletionError(
            "verification introduced dangerous deletions requiring exact confirmation: "
            + ", ".join(missing_after)
        )
        print(str(error))
        return DANGEROUS_DELETE_EXIT

    commands_passed = bool(results) and all(item.passed for item in results)
    passed_commands = {
        commands[index]
        for index, result in enumerate(results)
        if result.passed and index < len(commands)
    }
    declared_claims = claimed_commands(contract, cli_claims)
    declared_claim_binding, declared_coverage_detail = verification_coverage(
        assessment["verification_plan"]["required_behaviors"],
        declared_claims,
        passed_commands,
        tier=tier,
    )
    structured_claims = structured_contract_claimed_commands(contract)
    claim_binding, coverage_detail = verification_coverage(
        assessment["verification_plan"]["required_behaviors"],
        structured_claims if tier >= 1 else declared_claims,
        passed_commands,
        tier=tier,
    )
    process_converged = all(item.process_tree_converged for item in results)
    process_convergence = "complete" if process_converged else "uncertain"
    baseline_guard_satisfied = (
        not baseline_guard["changed"]
        and set(baseline_guard["missing"]).issubset(confirmed)
    )
    governed_evidence_complete = tier == 0 or (
        baseline is not None
        and contract is not None
        and root_cause_valid
        and baseline_guard_satisfied
    )
    workflow_sealed_evidence = (
        governed_evidence_complete
        and baseline_intake_sealed
        and contract_workflow_sealed
        and not hash_chain_errors
    )
    redacted_evidence = bool(
        capture_sensitive_change_quarantine
        or verification_capture_sensitive_change_quarantine
        or verification_sensitive_change_quarantine
    )
    semantic_review = {
        "unknown": "not-reviewed",
        "partial": "partial-operator-asserted",
        "reviewed": "operator-asserted",
    }[args.semantic_coverage]
    if (
        gate_errors
        or post_execution_errors
        or not commands_passed
        or not capture_preserved
    ):
        quality_status = "FAILED"
    elif not has_change:
        quality_status = "NO_CHANGE"
    elif process_convergence != "complete":
        quality_status = "UNVERIFIED"
    elif not governed_evidence_complete or claim_binding == "unverified":
        quality_status = "UNVERIFIED"
    elif claim_binding != "complete":
        quality_status = "COMMANDS_PASSED"
    elif redacted_evidence:
        quality_status = "REVIEW_REQUIRED_WITH_REDACTIONS"
    elif workflow_sealed_evidence and args.semantic_coverage == "reviewed":
        quality_status = "REVIEW_EVIDENCE_COMPLETE"
    elif args.semantic_coverage == "reviewed":
        quality_status = "SEMANTIC_REVIEW_ASSERTED"
    else:
        quality_status = "MECHANICALLY_VERIFIED"
    final_baseline_guard = (
        sensitive_preservation(baseline, snapshot_after)
        if baseline is not None
        else {"preserved": True, "missing": [], "changed": [], "added": []}
    )
    final_current_changes = captured_changes(snapshot_after, final_baseline_guard)
    final_partition = partition_task_changes(
        baseline=baseline,
        snapshot=snapshot_after,
        tracked_patch=patch_after,
        current_changes=final_current_changes,
        baseline_guard=final_baseline_guard,
    )
    patch = task_evidence_patch(
        baseline=baseline,
        tracked_patch=patch_after,
        untracked_patch=untracked_patch_after,
        task_changes=final_partition["task_changes"],
    )
    if len(patch) > args.max_patch_bytes:
        raise SystemExit(
            f"complete patch exceeds configured {args.max_patch_bytes}-byte budget"
        )
    risk_assessment = {
        key: value
        for key, value in assessment.items()
        if key not in {"changed_paths", "verification_plan"}
    }
    summary = {
        "format": SUMMARY_FORMAT,
        "schema_revision": SUMMARY_SCHEMA_REVISION,
        "producer_version": "4.1.0",
        "changed_files": changed_files,
        "risk": assessment["effective_risk"],
        "risk_assessment": risk_assessment,
        "tests": [asdict(item) for item in results],
        "verification_plan": assessment["verification_plan"],
        "verification_claims": coverage_detail,
        "claim_binding": claim_binding,
        "verification_coverage": claim_binding,
        "declared_verification_claims": declared_coverage_detail,
        "declared_claim_binding": declared_claim_binding,
        "semantic_coverage": args.semantic_coverage,
        "semantic_review": semantic_review,
        "mode": "strict" if args.strict else "advisory",
        "exit_policy": args.exit_policy,
        "commands_passed": commands_passed,
        "capture_preserved": capture_preserved,
        "verification_preserved_capture": capture_preserved,
        "evidence_files_preserved": evidence_files_preserved,
        "evidence_preservation_errors": evidence_preservation_errors,
        "repository_base_preserved_during_verification": repository_base_preserved,
        "post_execution_errors": post_execution_errors,
        "process_convergence": process_convergence,
        "detached_descendant_possible": True,
        "isolation": "process-group-only",
        "capture_limits": {
            "max_capture_seconds": args.max_capture_seconds,
            "max_git_seconds": args.max_git_seconds,
            "max_patch_bytes": args.max_patch_bytes,
            "max_sensitive_paths": args.max_sensitive_paths,
        },
        "capture_duration_seconds": round(
            capture_duration_before + capture_duration_after,
            6,
        ),
        "baseline_sensitive_preservation": baseline_guard,
        "sensitive_integrity": "metadata-observed",
        "sensitive_deletion_quarantine": sensitive_deletion_quarantine,
        "sensitive_change_quarantine": capture_sensitive_change_quarantine,
        "verification_sensitive_deletion_quarantine": (
            verification_sensitive_deletion_quarantine
        ),
        "verification_sensitive_change_quarantine": (
            verification_sensitive_change_quarantine
            or (
                verification_capture_sensitive_change_quarantine
                and not capture_sensitive_change_quarantine
            )
        ),
        "preexisting_changes": preexisting_changes,
        "removed_preexisting_paths": removed_preexisting_paths,
        "task_changes": task_changes,
        "change_partition": change_partition,
        "reviewability_policy": {
            "enabled": bool(baseline_reviewable),
            "paths": baseline_reviewable,
            "policy_provenance": (
                "intake-sealed"
                if baseline_reviewable and baseline_intake_sealed
                else "self-declared"
                if baseline_reviewable
                else None
            ),
            "captured_files_provenance": (
                "final-capture-observed" if baseline_reviewable else None
            ),
            "source": (
                "intake-sealed"
                if baseline_reviewable and baseline_intake_sealed
                else "self-declared"
                if baseline_reviewable
                else None
            ),
            "policy_sha256": (
                baseline.get("sensitive_policy_sha256")
                if baseline is not None and baseline_reviewable
                else None
            ),
            "captured_files": reviewable_metadata_after,
        },
        "baseline": {
            "required": bool(args.strict and tier >= 1),
            "provided": baseline is not None,
            "format": baseline.get("format") if baseline is not None else None,
            "sha256": baseline_sha256,
            "run_id": baseline.get("run_id") if baseline is not None else None,
            "nonce": baseline.get("nonce") if baseline is not None else None,
            "task_sha256": baseline.get("task_sha256") if baseline is not None else None,
            "age_seconds": baseline_age_seconds,
            "freshness": baseline_freshness,
            "git": baseline.get("git") if baseline is not None else None,
            "current_git": current_git,
            "verification_git": current_git_after,
            "repository_base_stable": (
                baseline is None
                or (
                    baseline.get("git") == current_git
                    and baseline.get("git") == current_git_after
                )
            ),
        },
        "change_contract": {
            "required": bool(args.strict and tier >= 1),
            "provided": contract is not None,
            "sha256": contract_sha256,
            "run_id": contract.get("run_id") if contract is not None else None,
            "nonce": contract.get("nonce") if contract is not None else None,
            "task_sha256": contract.get("task_sha256") if contract is not None else None,
            "baseline_sha256": contract.get("baseline_sha256") if contract is not None else None,
            "contract_sha256": contract.get("contract_sha256") if contract is not None else None,
            "scope_valid": contract_scope_valid,
            "scope_violations": scope,
            "root_cause_alignment": root_cause_alignment,
            "root_cause_alignment_valid": root_cause_valid,
            "hash_chain_valid": not hash_chain_errors,
            "hash_chain_errors": hash_chain_errors,
        },
        "review_manifest": review_manifest,
        "evidence_provenance": {
            "baseline": "intake-sealed" if baseline_intake_sealed else "self-declared",
            "change_contract": (
                "workflow-sealed" if contract_workflow_sealed else "self-declared"
            ),
            "verification_claims": (
                "workflow-sealed"
                if contract_workflow_sealed and claim_binding == "complete"
                else "self-declared"
            ),
            "semantic_review": semantic_review,
        },
        "hash_chain": {
            "baseline_sha256": baseline_sha256,
            "change_contract_sha256": contract_sha256,
            "task_sha256": expected_task_sha256,
            "run_id": baseline.get("run_id") if baseline is not None else None,
            "nonce": baseline.get("nonce") if baseline is not None else None,
            "valid": not hash_chain_errors,
            "errors": hash_chain_errors,
        },
        "repository_capture": {
            "identity": snapshot_identity(snapshot_after),
            "untracked": snapshot_after["untracked"],
            "sensitive_paths": snapshot_after["sensitive_paths"],
            "bounds": snapshot_after["bounds"],
        },
        "quality_status": quality_status,
        "evidence_complete": quality_status == "REVIEW_EVIDENCE_COMPLETE",
        "remaining_risks": list(args.remaining_risk),
        "dangerous_deletions_confirmed": confirmed,
        "allow_no_change": bool(args.allow_no_change),
        "passed": quality_status == "REVIEW_EVIDENCE_COMPLETE",
    }
    summary["process_exit_code"] = (
        0
        if args.exit_policy == "bundle" and quality_status != "FAILED"
        else QUALITY_EXIT_CODES[quality_status]
    )
    try:
        output_rechecked = validate_no_symlink_chain(
            output_lexical,
            label="output directory",
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
            label="output directory",
        )
        if output_resolved_after != output:
            raise ValueError("output directory target changed during verification")
        output_preflight(output_resolved_after)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"output path changed during verification: {exc}") from exc
    write_bundle(output, patch=patch, log=log, summary=summary)
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return int(summary["process_exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
