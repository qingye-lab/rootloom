#!/usr/bin/env python3
"""Prepare and finish strict Rootloom evidence with the frozen evidence formats."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any


RESOURCE_ROOT = Path(__file__).resolve().parent
BEGIN_REVIEW = RESOURCE_ROOT / "begin_review.py"
SEAL_CONTRACT = RESOURCE_ROOT / "seal_contract.py"
FINALIZE_CHANGE = RESOURCE_ROOT / "finalize_change.py"
sys.path.insert(0, str(RESOURCE_ROOT))

from runner.change_contract import load_change_contract
from runner.evidence_paths import fsync_directory, validate_no_symlink_chain
from runner.review_run import (
    CONTRACT_DRAFT_SENTINEL,
    pretty_json_bytes,
    read_json_no_follow,
)
from runner.verification import split_command


CLAIM_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
EVIDENCE_KINDS = (
    "regression-test",
    "unit-test",
    "integration-test",
    "contract-test",
    "manual-review",
    "static-check",
    "build",
    "other",
)
MAX_EVIDENCE_DESCRIPTION_CHARS = 2_000


class OrchestrationError(RuntimeError):
    """A compact user-facing orchestration failure."""


def _run_helper(path: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, str(path), *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise OrchestrationError(
            f"{path.name} failed with exit {completed.returncode}: {detail}"
        )
    return completed


def _claim_descriptions(args: argparse.Namespace) -> dict[str, str]:
    claims = {
        "primary-behavior": args.primary_evidence,
        "owning-invariant": args.invariant_evidence,
        "adjacent-path": args.adjacent_evidence,
    }
    for raw in args.claim:
        claim_id, separator, description = raw.partition("=")
        claim_id = claim_id.strip()
        description = description.strip()
        if (
            not separator
            or CLAIM_ID.fullmatch(claim_id) is None
            or not description
        ):
            raise OrchestrationError(
                "--claim must use a safe CLAIM-ID=EXPECTED-EVIDENCE value"
            )
        if claim_id in claims:
            raise OrchestrationError(f"duplicate evidence claim: {claim_id}")
        claims[claim_id] = description
    for claim_id, description in claims.items():
        if (
            not description.strip()
            or len(description) > MAX_EVIDENCE_DESCRIPTION_CHARS
        ):
            raise OrchestrationError(
                f"evidence description for {claim_id} must contain 1-"
                f"{MAX_EVIDENCE_DESCRIPTION_CHARS} characters"
            )
    return claims


def _draft_identity(path: Path) -> tuple[int, int, int, int, int]:
    observed = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(observed.st_mode):
        raise OrchestrationError("change-contract draft must be a regular file")
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )


def _replace_draft(
    path: Path,
    *,
    expected_identity: tuple[int, int, int, int, int],
    payload: dict[str, Any],
) -> None:
    temporary = path.parent / f".{path.name}.orchestrator-{os.getpid()}"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(temporary, flags, 0o600)
    try:
        try:
            encoded = pretty_json_bytes(payload)
            offset = 0
            while offset < len(encoded):
                written = os.write(descriptor, encoded[offset:])
                if written <= 0:
                    raise OSError("short write while preparing change contract")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            load_change_contract(temporary)
        except (OSError, ValueError) as exc:
            raise OrchestrationError(
                f"generated change contract is invalid: {exc}"
            ) from exc
        if _draft_identity(path) != expected_identity:
            raise OrchestrationError(
                "change-contract draft changed while it was being prepared"
            )
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _placeholder_draft(
    review_dir: Path,
    *,
    expected_paths: list[str],
) -> tuple[Path, dict[str, Any], tuple[int, int, int, int, int]]:
    draft_path = review_dir / "change-contract.draft.json"
    before = _draft_identity(draft_path)
    try:
        draft, _raw = read_json_no_follow(
            draft_path,
            label="change-contract draft",
        )
    except (OSError, ValueError) as exc:
        raise OrchestrationError(str(exc)) from exc
    after = _draft_identity(draft_path)
    if before != after:
        raise OrchestrationError("change-contract draft changed while it was read")
    expected_command = {"verify-primary": CONTRACT_DRAFT_SENTINEL}
    expected_claim = {
        "primary-behavior": [
            {
                "id": "primary-behavior",
                "command_ids": ["verify-primary"],
                "target": CONTRACT_DRAFT_SENTINEL,
                "expected_evidence": CONTRACT_DRAFT_SENTINEL,
                "evidence_kind": "manual-review",
            }
        ]
    }
    if (
        draft.get("format") != "rootloom-change-contract-v1"
        or draft.get("allowed_paths") != expected_paths
        or draft.get("verification_commands") != expected_command
        or draft.get("verification_claims") != expected_claim
    ):
        raise OrchestrationError(
            "review directory does not contain the exact Rootloom placeholder draft"
        )
    return draft_path, draft, after


def prepare(args: argparse.Namespace) -> int:
    claims = _claim_descriptions(args)
    if not args.path:
        raise OrchestrationError("prepare requires at least one --path")
    if not args.verify.strip():
        raise OrchestrationError("--verify must not be empty")
    try:
        split_command(args.verify)
    except ValueError as exc:
        raise OrchestrationError(f"invalid verification command: {exc}") from exc
    target = args.target.strip()
    if not target or target not in args.verify:
        raise OrchestrationError(
            "--target must be a non-empty literal substring of --verify"
        )
    review_dir = args.review_dir.expanduser()
    begin_argv = [
        "--repo",
        str(args.repo),
        "--task",
        args.task,
        "--output",
        str(review_dir),
    ]
    for path in args.path:
        begin_argv.extend(["--path", path])
    if args.allow_dirty_baseline:
        begin_argv.append("--allow-dirty-baseline")
    _run_helper(BEGIN_REVIEW, begin_argv)
    try:
        resolved_review = validate_no_symlink_chain(
            review_dir,
            label="review directory",
            leaf_may_be_missing=False,
        )
    except ValueError as exc:
        raise OrchestrationError(str(exc)) from exc
    draft_path, draft, identity = _placeholder_draft(
        resolved_review,
        expected_paths=args.path,
    )
    bindings = {
        claim_id: [
            {
                "id": claim_id,
                "command_ids": ["verify-primary"],
                "target": target,
                "expected_evidence": description,
                "evidence_kind": args.evidence_kind,
            }
        ]
        for claim_id, description in claims.items()
    }
    contract = {
        **draft,
        "root_cause_alignment": args.root_cause_alignment,
        "verification_commands": {"verify-primary": args.verify},
        "verification_claims": bindings,
    }
    _replace_draft(
        draft_path,
        expected_identity=identity,
        payload=contract,
    )
    _run_helper(
        SEAL_CONTRACT,
        ["--review-dir", str(resolved_review)],
    )
    print(
        json.dumps(
            {
                "status": "prepared-and-sealed",
                "review_dir": str(resolved_review),
                "baseline": str(resolved_review / "baseline.json"),
                "change_contract": str(
                    resolved_review / "change-contract.json"
                ),
                "claim_count": len(claims),
                "next": "implement the scoped change, then run finish",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


def finish(args: argparse.Namespace) -> int:
    if not args.semantic_review_confirmed:
        raise OrchestrationError(
            "finish requires --semantic-review-confirmed after actual semantic review"
        )
    try:
        review_dir = validate_no_symlink_chain(
            args.review_dir,
            label="review directory",
            leaf_may_be_missing=False,
        )
    except ValueError as exc:
        raise OrchestrationError(str(exc)) from exc
    contract_path = review_dir / "change-contract.json"
    try:
        contract = load_change_contract(contract_path)
    except (OSError, ValueError) as exc:
        raise OrchestrationError(str(exc)) from exc
    argv = [
        "--repo",
        str(args.repo),
        "--output",
        str(args.output),
        "--task",
        args.task,
        "--baseline",
        str(review_dir / "baseline.json"),
        "--change-contract",
        str(contract_path),
        "--strict",
        "--semantic-coverage",
        "reviewed",
        "--timeout",
        str(args.timeout),
    ]
    for command in contract["verification_commands"].values():
        argv.extend(["--verify", command])
    for risk in args.remaining_risk:
        argv.extend(["--remaining-risk", risk])
    if args.allow_no_change:
        argv.append("--allow-no-change")
    completed = subprocess.run(
        [sys.executable, str(FINALIZE_CHANGE), *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    summary_path = args.output.expanduser() / "summary.json"
    if not summary_path.is_file() or summary_path.is_symlink():
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise OrchestrationError(
            f"finalize_change.py produced no summary "
            f"(exit {completed.returncode}): {detail}"
        )
    try:
        summary = json.loads(summary_path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError(f"invalid final summary: {exc}") from exc
    print(
        json.dumps(
            {
                "status": summary.get("quality_status"),
                "passed": summary.get("passed"),
                "evidence_complete": summary.get("evidence_complete"),
                "verification_coverage": summary.get("verification_coverage"),
                "output": str(args.output.expanduser()),
                "summary": str(summary_path),
                "process_exit_code": completed.returncode,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="create intake, complete the standard contract, and seal it",
    )
    prepare_parser.add_argument("--repo", type=Path, required=True)
    prepare_parser.add_argument("--task", required=True)
    prepare_parser.add_argument("--review-dir", type=Path, required=True)
    prepare_parser.add_argument("--path", action="append", default=[])
    prepare_parser.add_argument("--verify", required=True)
    prepare_parser.add_argument("--target", required=True)
    prepare_parser.add_argument("--primary-evidence", required=True)
    prepare_parser.add_argument("--invariant-evidence", required=True)
    prepare_parser.add_argument("--adjacent-evidence", required=True)
    prepare_parser.add_argument(
        "--root-cause-alignment",
        choices=("PASS", "NOT_APPLICABLE"),
        default="NOT_APPLICABLE",
    )
    prepare_parser.add_argument(
        "--claim",
        action="append",
        default=[],
        metavar="CLAIM-ID=EXPECTED-EVIDENCE",
    )
    prepare_parser.add_argument(
        "--evidence-kind",
        choices=EVIDENCE_KINDS,
        default="unit-test",
    )
    prepare_parser.add_argument("--allow-dirty-baseline", action="store_true")

    finish_parser = subparsers.add_parser(
        "finish",
        help="run sealed verification and write the strict frozen-format bundle",
    )
    finish_parser.add_argument("--repo", type=Path, required=True)
    finish_parser.add_argument("--task", required=True)
    finish_parser.add_argument("--review-dir", type=Path, required=True)
    finish_parser.add_argument("--output", type=Path, required=True)
    finish_parser.add_argument(
        "--semantic-review-confirmed",
        action="store_true",
        required=True,
        help="explicitly assert that semantic review was actually completed",
    )
    finish_parser.add_argument("--remaining-risk", action="append", default=[])
    finish_parser.add_argument("--allow-no-change", action="store_true")
    finish_parser.add_argument("--timeout", type=int, default=300)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.operation == "prepare":
            return prepare(args)
        return finish(args)
    except (OSError, OrchestrationError) as exc:
        print(f"Rootloom evidence orchestration failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
