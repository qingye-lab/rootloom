"""Schemas and no-follow I/O for governed review manifests and contract seals."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any
import uuid

from .strict_json import parse_json_object


REVIEW_MANIFEST_FORMAT = "rootloom-review-run-v2"
CONTRACT_SEAL_FORMAT = "rootloom-contract-seal-v1"
CONTRACT_HASH_BASIS = "canonical-json-without-contract_sha256"
CONTRACT_DRAFT_SENTINEL = "__ROOTLOOM_CONTRACT_PLACEHOLDER__"
MAX_REVIEW_FILE_BYTES = 256 * 1024
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
NONCE_PATTERN = re.compile(r"[0-9a-f]{32}")
REVIEW_MANIFEST_FIELDS = {
    "format",
    "run_id",
    "nonce",
    "task_sha256",
    "baseline",
    "baseline_sha256",
    "change_contract_draft",
    "next_step",
}
CONTRACT_SEAL_FIELDS = {
    "format",
    "hash_basis",
    "run_id",
    "nonce",
    "task_sha256",
    "baseline_sha256",
    "review_manifest_sha256",
    "change_contract",
    "contract_sha256",
    "contract_file_sha256",
}


def pretty_json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode("ascii")


def write_new_bytes(path: Path, value: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    completed = False
    try:
        view = memoryview(value)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"short write while creating {path}")
            view = view[written:]
        os.fsync(descriptor)
        completed = True
    finally:
        os.close(descriptor)
        if not completed:
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    write_new_bytes(path, pretty_json_bytes(payload))


def read_json_no_follow(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError(f"{label} must be a regular file")
        raw = bytearray()
        while len(raw) <= MAX_REVIEW_FILE_BYTES:
            chunk = os.read(
                descriptor,
                min(64 * 1024, MAX_REVIEW_FILE_BYTES + 1 - len(raw)),
            )
            if not chunk:
                break
            raw.extend(chunk)
        after = os.fstat(descriptor)
        if (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValueError(f"{label} changed during read")
        if len(raw) > MAX_REVIEW_FILE_BYTES or after.st_size > MAX_REVIEW_FILE_BYTES:
            raise ValueError(f"{label} exceeds byte budget")
    finally:
        os.close(descriptor)
    payload = parse_json_object(bytes(raw), label=label, encoding="ascii")
    return payload, bytes(raw)


def _validate_common_identity(payload: dict[str, Any], *, label: str) -> None:
    run_id = payload.get("run_id")
    try:
        parsed = uuid.UUID(str(run_id))
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{label} run_id must be a canonical UUID") from exc
    if str(parsed) != run_id:
        raise ValueError(f"{label} run_id must be a canonical UUID")
    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or NONCE_PATTERN.fullmatch(nonce) is None:
        raise ValueError(f"{label} nonce must be 32 lowercase hexadecimal characters")
    for field in ("task_sha256", "baseline_sha256"):
        value = payload.get(field)
        if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError(
                f"{label} {field} must be 64 lowercase hexadecimal characters"
            )


def validate_review_manifest(
    payload: dict[str, Any],
    *,
    baseline_name: str,
    baseline_sha256: str,
    baseline: dict[str, Any],
) -> None:
    if set(payload) != REVIEW_MANIFEST_FIELDS:
        raise ValueError("review manifest has unexpected or missing fields")
    if payload.get("format") != REVIEW_MANIFEST_FORMAT:
        raise ValueError("review manifest format is invalid")
    _validate_common_identity(payload, label="review manifest")
    expected = {
        "run_id": baseline.get("run_id"),
        "nonce": baseline.get("nonce"),
        "task_sha256": baseline.get("task_sha256"),
        "baseline": baseline_name,
        "baseline_sha256": baseline_sha256,
        "change_contract_draft": "change-contract.draft.json",
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"review manifest {field} does not match")
    next_step = payload.get("next_step")
    if not isinstance(next_step, str) or not next_step.strip():
        raise ValueError("review manifest next_step must be a nonempty string")


def validate_contract_seal(
    payload: dict[str, Any],
    *,
    baseline: dict[str, Any],
    baseline_sha256: str,
    review_manifest_sha256: str,
    contract_sha256: str,
    contract_file_sha256: str,
) -> None:
    if set(payload) != CONTRACT_SEAL_FIELDS:
        raise ValueError("contract seal has unexpected or missing fields")
    if payload.get("format") != CONTRACT_SEAL_FORMAT:
        raise ValueError("contract seal format is invalid")
    if payload.get("hash_basis") != CONTRACT_HASH_BASIS:
        raise ValueError("contract seal hash_basis is invalid")
    _validate_common_identity(payload, label="contract seal")
    for field in (
        "review_manifest_sha256",
        "contract_sha256",
        "contract_file_sha256",
    ):
        value = payload.get(field)
        if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError(
                f"contract seal {field} must be 64 lowercase hexadecimal characters"
            )
    expected = {
        "run_id": baseline.get("run_id"),
        "nonce": baseline.get("nonce"),
        "task_sha256": baseline.get("task_sha256"),
        "baseline_sha256": baseline_sha256,
        "review_manifest_sha256": review_manifest_sha256,
        "change_contract": "change-contract.json",
        "contract_sha256": contract_sha256,
        "contract_file_sha256": contract_file_sha256,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"contract seal {field} does not match")


def file_bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
