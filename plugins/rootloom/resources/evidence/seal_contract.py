#!/usr/bin/env python3
"""Validate and immutably seal a Rootloom change-contract draft."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from runner.baseline import (
    BASELINE_FORMAT_V2,
    BASELINE_FORMAT_V3,
    BASELINE_FORMAT_V4,
    read_baseline_payload_with_hash,
)
from runner.change_contract import contract_sha256, load_change_contract
from runner.evidence_paths import (
    fsync_directory,
    validate_no_symlink_chain,
    validate_outside_repository_storage,
)
from runner.review_run import (
    CONTRACT_DRAFT_SENTINEL,
    CONTRACT_HASH_BASIS,
    CONTRACT_SEAL_FORMAT,
    file_bytes_sha256,
    pretty_json_bytes,
    read_json_no_follow,
    validate_contract_seal,
    validate_review_manifest,
    write_new_bytes,
    write_new_json,
)


LEGACY_DRAFT_PLACEHOLDERS = {
    "TODO",
    "TODO replace with repository test command for TODO",
    "TODO replace before finalization",
}


def contains_contract_placeholder(value: object) -> bool:
    if isinstance(value, str):
        return value == CONTRACT_DRAFT_SENTINEL or value in LEGACY_DRAFT_PLACEHOLDERS
    if isinstance(value, list):
        return any(contains_contract_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(
            contains_contract_placeholder(key) or contains_contract_placeholder(item)
            for key, item in value.items()
        )
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument(
        "--recover",
        action="store_true",
        help="validate and complete an exact interrupted contract/seal publication",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        review_dir = validate_no_symlink_chain(
            args.review_dir,
            label="review directory",
            leaf_may_be_missing=False,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not review_dir.is_dir():
        raise SystemExit(f"review directory must be a directory: {review_dir}")
    baseline_path = review_dir / "baseline.json"
    manifest_path = review_dir / "review.json"
    draft_path = review_dir / "change-contract.draft.json"
    contract_path = review_dir / "change-contract.json"
    seal_path = review_dir / "contract.seal.json"
    contract_exists = contract_path.exists() or contract_path.is_symlink()
    seal_exists = seal_path.exists() or seal_path.is_symlink()
    if not args.recover and contract_exists:
        raise SystemExit(f"sealed change contract already exists: {contract_path}")
    if not args.recover and seal_exists:
        raise SystemExit(f"contract seal already exists: {seal_path}")
    if args.recover and not contract_exists:
        if seal_exists:
            raise SystemExit(
                "cannot recover a contract seal without its sealed change contract"
            )
        raise SystemExit(
            "no interrupted contract publication exists; seal without --recover"
        )
    try:
        baseline, baseline_sha256 = read_baseline_payload_with_hash(baseline_path)
        sealed_baselines = {
            BASELINE_FORMAT_V2: "operator-sealed",
            BASELINE_FORMAT_V3: "intake-sealed",
            BASELINE_FORMAT_V4: "intake-sealed",
        }
        if baseline.get("evidence_provenance") != sealed_baselines.get(
            baseline.get("format")
        ):
            raise ValueError(
                "contract sealing requires an intake-sealed baseline v3 or v4 "
                "or compatible legacy sealed baseline v2"
            )
        repository = baseline["repository"]
        review_storage = validate_outside_repository_storage(
            review_dir,
            repository_roots=(
                Path(repository["worktree"]),
                Path(repository["git_common_dir"]),
            ),
            label="review directory",
        )
        manifest, manifest_raw = read_json_no_follow(
            manifest_path, label="review manifest"
        )
        validate_review_manifest(
            manifest,
            baseline_name=baseline_path.name,
            baseline_sha256=baseline_sha256,
            baseline=baseline,
        )
        contract = load_change_contract(draft_path)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    raw_contract = dict(contract["raw_payload"])
    if "contract_sha256" in raw_contract:
        raise SystemExit("change-contract draft must not declare contract_sha256")
    if contains_contract_placeholder(raw_contract):
        raise SystemExit("change-contract draft still contains a Rootloom contract placeholder")
    expected_identity = {
        "run_id": baseline.get("run_id"),
        "nonce": baseline.get("nonce"),
        "task_sha256": baseline.get("task_sha256"),
        "baseline_sha256": baseline_sha256,
    }
    for field, value in expected_identity.items():
        if raw_contract.get(field) != value:
            raise SystemExit(f"change-contract draft {field} does not match baseline")
    sealed_contract = dict(raw_contract)
    sealed_contract["contract_sha256"] = contract_sha256(sealed_contract)
    contract_bytes = pretty_json_bytes(sealed_contract)
    seal = {
        "format": CONTRACT_SEAL_FORMAT,
        "hash_basis": CONTRACT_HASH_BASIS,
        "run_id": baseline["run_id"],
        "nonce": baseline["nonce"],
        "task_sha256": baseline["task_sha256"],
        "baseline_sha256": baseline_sha256,
        "review_manifest_sha256": file_bytes_sha256(manifest_raw),
        "change_contract": contract_path.name,
        "contract_sha256": sealed_contract["contract_sha256"],
        "contract_file_sha256": file_bytes_sha256(contract_bytes),
    }
    contract_created = False
    try:
        review_rechecked = validate_no_symlink_chain(
            args.review_dir,
            label="review directory",
            leaf_may_be_missing=False,
        )
        review_storage_after = validate_outside_repository_storage(
            review_rechecked,
            repository_roots=(
                Path(repository["worktree"]),
                Path(repository["git_common_dir"]),
            ),
            label="review directory",
        )
        if review_storage_after != review_storage:
            raise ValueError("review directory target changed before sealing")
        if contract_exists:
            existing_contract = load_change_contract(contract_path)
            if (
                existing_contract["raw_payload"] != sealed_contract
                or existing_contract["actual_contract_file_sha256"]
                != seal["contract_file_sha256"]
            ):
                raise ValueError(
                    "existing sealed change contract does not match the current draft and intake"
                )
        else:
            write_new_bytes(contract_path, contract_bytes)
            contract_created = True
        if seal_exists:
            existing_seal, existing_seal_raw = read_json_no_follow(
                seal_path,
                label="contract seal",
            )
            validate_contract_seal(
                existing_seal,
                baseline=baseline,
                baseline_sha256=baseline_sha256,
                review_manifest_sha256=seal["review_manifest_sha256"],
                contract_sha256=seal["contract_sha256"],
                contract_file_sha256=seal["contract_file_sha256"],
            )
            if existing_seal_raw != pretty_json_bytes(seal):
                raise ValueError("existing contract seal does not match expected bytes")
        else:
            write_new_json(seal_path, seal)
        fsync_directory(review_dir)
    except (OSError, ValueError) as exc:
        if contract_created and not seal_path.exists():
            try:
                contract_path.unlink()
            except FileNotFoundError:
                pass
        raise SystemExit(str(exc)) from exc
    print(json.dumps(seal, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
