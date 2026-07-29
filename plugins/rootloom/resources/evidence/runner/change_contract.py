"""Machine-checkable scope and verification declarations for Tier 1/2 changes."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Any
import uuid

from .baseline import canonical_json_bytes
from .strict_json import parse_json_object


CHANGE_CONTRACT_FORMAT = "rootloom-change-contract-v1"
MAX_CONTRACT_BYTES = 1024 * 1024
MAX_PATTERNS = 200
MAX_VERIFICATIONS = 20
MAX_COMMAND_CHARS = 8192
MAX_PATTERN_CHARS = 4096
CLAIM_ALIASES = {
    "primary": "primary-behavior",
    "invariant": "owning-invariant",
    "adjacent": "adjacent-path",
}
ROOT_CAUSE_VALUES = {"PASS", "NOT_APPLICABLE"}
EVIDENCE_KINDS = {
    "regression-test",
    "unit-test",
    "integration-test",
    "contract-test",
    "manual-review",
    "static-check",
    "build",
    "other",
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
NONCE_PATTERN = re.compile(r"[0-9a-f]{32}")
CONTRACT_FIELDS = {
    "format",
    "run_id",
    "nonce",
    "baseline_sha256",
    "task_sha256",
    "allowed_paths",
    "forbidden_paths",
    "root_cause_alignment",
    "verification_commands",
    "verification_claims",
    "contract_sha256",
}
CLAIM_BINDING_FIELDS = {
    "id",
    "command_ids",
    "target",
    "expected_evidence",
    "evidence_kind",
}
CLAIM_BINDING_REQUIRED_FIELDS = CLAIM_BINDING_FIELDS - {"id"}


def contract_sha256(payload: dict[str, Any]) -> str:
    normalized = dict(payload)
    normalized.pop("contract_sha256", None)
    return hashlib.sha256(canonical_json_bytes(normalized)).hexdigest()


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink():
        raise ValueError(f"change contract must not be a symlink: {path}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError(f"change contract must be a regular file: {path}")
        raw = bytearray()
        while len(raw) <= MAX_CONTRACT_BYTES:
            chunk = os.read(descriptor, min(64 * 1024, MAX_CONTRACT_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        after = os.fstat(descriptor)
        if (
            (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
                opened.st_mtime_ns,
                opened.st_ctime_ns,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
        ):
            raise ValueError(f"change contract changed during read: {path}")
        if len(raw) > MAX_CONTRACT_BYTES or after.st_size > MAX_CONTRACT_BYTES:
            raise ValueError(f"change contract exceeds {MAX_CONTRACT_BYTES} bytes: {path}")
    finally:
        os.close(descriptor)
    payload = parse_json_object(
        bytes(raw), label="change contract", encoding="utf-8"
    )
    return payload, bytes(raw)


def _normalize_pattern(raw: str, *, field: str) -> str:
    value = raw.strip().replace("\\", "/")
    parts = value.split("/")
    if (
        not value
        or len(value) > MAX_PATTERN_CHARS
        or value.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
        or any("**" in part and part != "**" for part in parts)
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{field} contains an unsafe repository-relative glob: {raw!r}")
    return value


def _string_list(payload: dict[str, Any], field: str, *, required: bool) -> list[str]:
    raw = payload.get(field)
    if raw is None and not required:
        return []
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ValueError(f"change contract {field} must be a string list")
    if required and not raw:
        raise ValueError(f"change contract {field} must not be empty")
    if len(raw) > MAX_PATTERNS:
        raise ValueError(f"change contract {field} exceeds {MAX_PATTERNS} entries")
    normalized = [_normalize_pattern(item, field=field) for item in raw]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"change contract {field} must not contain duplicates")
    return normalized


def load_change_contract(path: Path) -> dict[str, Any]:
    payload, raw = _read_json(path)
    unknown = set(payload) - CONTRACT_FIELDS
    if unknown:
        raise ValueError(
            "change contract has unexpected fields: " + ", ".join(sorted(unknown))
        )
    if payload.get("format") != CHANGE_CONTRACT_FORMAT:
        raise ValueError(f"change contract format must be {CHANGE_CONTRACT_FORMAT}")
    actual_sha256 = contract_sha256(payload)
    declared_sha256 = payload.get("contract_sha256")
    if "contract_sha256" in payload:
        if (
            not isinstance(declared_sha256, str)
            or SHA256_PATTERN.fullmatch(declared_sha256) is None
        ):
            raise ValueError(
                "change contract contract_sha256 must be 64 lowercase hexadecimal characters"
            )
        if declared_sha256 != actual_sha256:
            raise ValueError("change contract contract_sha256 does not match content")
    for field in ("baseline_sha256", "task_sha256"):
        value = payload.get(field)
        if value is not None and (
            not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None
        ):
            raise ValueError(
                f"change contract {field} must be 64 lowercase hexadecimal characters"
            )
    run_id = payload.get("run_id")
    if run_id is not None:
        try:
            parsed_run_id = uuid.UUID(str(run_id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("change contract run_id must be a canonical UUID") from exc
        if str(parsed_run_id) != run_id:
            raise ValueError("change contract run_id must be a canonical UUID")
    nonce = payload.get("nonce")
    if nonce is not None and (
        not isinstance(nonce, str) or NONCE_PATTERN.fullmatch(nonce) is None
    ):
        raise ValueError("change contract nonce must be 32 lowercase hexadecimal characters")
    allowed = _string_list(payload, "allowed_paths", required=True)
    forbidden = _string_list(payload, "forbidden_paths", required=False)
    alignment = payload.get("root_cause_alignment")
    if alignment not in ROOT_CAUSE_VALUES:
        raise ValueError(
            "change contract root_cause_alignment must be PASS or NOT_APPLICABLE"
        )
    commands = payload.get("verification_commands", {})
    if not isinstance(commands, dict) or any(
        not isinstance(key, str)
        or not key.strip()
        or not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_COMMAND_CHARS
        for key, value in commands.items()
    ):
        raise ValueError("change contract verification_commands must map IDs to commands")
    if len(commands) > MAX_VERIFICATIONS:
        raise ValueError(
            f"change contract supports at most {MAX_VERIFICATIONS} verification commands"
        )
    claims = payload.get("verification_claims")
    if not isinstance(claims, dict) or not claims:
        raise ValueError("change contract verification_claims must not be empty")
    normalized_claims: dict[str, list[str]] = {}
    normalized_bindings: dict[str, list[dict[str, Any]]] = {}
    for raw_claim, references in claims.items():
        if not isinstance(raw_claim, str) or not raw_claim.strip():
            raise ValueError("change contract claim IDs must be nonempty strings")
        claim_id = CLAIM_ALIASES.get(raw_claim, raw_claim)
        if claim_id in normalized_claims:
            raise ValueError(
                f"change contract verification_claims contains duplicate alias {claim_id}"
            )
        if not isinstance(references, list) or not references:
            raise ValueError("change contract claims must contain verification IDs")
        command_ids: list[str] = []
        bindings: list[dict[str, Any]] = []
        for item in references:
            if isinstance(item, str):
                if not item.strip():
                    raise ValueError("change contract claims must contain verification IDs")
                command_ids.append(item)
                continue
            if not isinstance(item, dict):
                raise ValueError("change contract claim bindings must be strings or objects")
            if not CLAIM_BINDING_REQUIRED_FIELDS.issubset(item) or not set(
                item
            ).issubset(CLAIM_BINDING_FIELDS):
                raise ValueError(
                    "change contract claim binding has unexpected or missing fields"
                )
            raw_commands = item.get("command_ids")
            if not isinstance(raw_commands, list) or not raw_commands or any(
                not isinstance(command_id, str) or not command_id.strip()
                for command_id in raw_commands
            ):
                raise ValueError("change contract claim binding command_ids must be nonempty")
            if len(set(raw_commands)) != len(raw_commands):
                raise ValueError("change contract claim binding command_ids must be unique")
            binding_id = item.get("id", claim_id)
            if not isinstance(binding_id, str) or not binding_id.strip():
                raise ValueError("change contract claim binding id must be nonempty")
            target = item.get("target")
            expected = item.get("expected_evidence")
            evidence_kind = item.get("evidence_kind")
            if not isinstance(target, str) or not target.strip():
                raise ValueError("change contract claim binding target must be nonempty")
            if not isinstance(expected, str) or not expected.strip():
                raise ValueError(
                    "change contract claim binding expected_evidence must be nonempty"
                )
            if evidence_kind not in EVIDENCE_KINDS:
                raise ValueError("change contract claim binding evidence_kind is invalid")
            command_ids.extend(raw_commands)
            bindings.append(
                {
                    "id": binding_id,
                    "command_ids": list(raw_commands),
                    "target": target,
                    "expected_evidence": expected,
                    "evidence_kind": evidence_kind,
                }
            )
        missing = sorted(set(command_ids) - set(commands))
        if missing:
            raise ValueError(
                f"change contract claim {raw_claim} references unknown verifications: "
                + ", ".join(missing)
            )
        for binding in bindings:
            for command_id in binding["command_ids"]:
                command = commands[command_id]
                if binding["target"] not in command:
                    raise ValueError(
                        f"change contract claim {raw_claim} target is not present in "
                        f"verification command {command_id}"
                    )
        normalized_claims[claim_id] = list(command_ids)
        normalized_bindings[claim_id] = bindings
    return {
        **payload,
        "raw_payload": dict(payload),
        "allowed_paths": allowed,
        "forbidden_paths": forbidden,
        "verification_commands": dict(commands),
        "verification_claims": normalized_claims,
        "verification_claim_bindings": normalized_bindings,
        "actual_contract_sha256": actual_sha256,
        "actual_contract_file_sha256": hashlib.sha256(raw).hexdigest(),
        "declared_contract_sha256_valid": declared_sha256 == actual_sha256,
    }


def path_matches(path: str, pattern: str) -> bool:
    path_parts = tuple(path.split("/"))
    pattern_parts = tuple(pattern.split("/"))
    path_index = 0
    pattern_index = 0
    globstar_index = -1
    retry_path_index = -1
    while path_index < len(path_parts):
        if (
            pattern_index < len(pattern_parts)
            and pattern_parts[pattern_index] != "**"
            and _segment_matches(
                path_parts[path_index], pattern_parts[pattern_index]
            )
        ):
            path_index += 1
            pattern_index += 1
        elif pattern_index < len(pattern_parts) and pattern_parts[pattern_index] == "**":
            globstar_index = pattern_index
            retry_path_index = path_index
            pattern_index += 1
        elif globstar_index >= 0:
            retry_path_index += 1
            path_index = retry_path_index
            pattern_index = globstar_index + 1
        else:
            return False
    while pattern_index < len(pattern_parts) and pattern_parts[pattern_index] == "**":
        pattern_index += 1
    return pattern_index == len(pattern_parts)


def _segment_matches(value: str, pattern: str) -> bool:
    """Match only the documented segment-local `*` and `?` wildcards."""

    value_index = 0
    pattern_index = 0
    star_index = -1
    retry_value_index = -1
    while value_index < len(value):
        if pattern_index < len(pattern) and (
            pattern[pattern_index] == "?" or pattern[pattern_index] == value[value_index]
        ):
            value_index += 1
            pattern_index += 1
        elif pattern_index < len(pattern) and pattern[pattern_index] == "*":
            star_index = pattern_index
            retry_value_index = value_index
            pattern_index += 1
        elif star_index >= 0:
            retry_value_index += 1
            value_index = retry_value_index
            pattern_index = star_index + 1
        else:
            return False
    while pattern_index < len(pattern) and pattern[pattern_index] == "*":
        pattern_index += 1
    return pattern_index == len(pattern)


def scope_violations(
    contract: dict[str, Any], changes: list[dict[str, str]]
) -> dict[str, list[str]]:
    paths = {
        item[field]
        for item in changes
        for field in ("path", "original_path")
        if item.get(field)
    }
    outside = sorted(
        path
        for path in paths
        if not any(path_matches(path, pattern) for pattern in contract["allowed_paths"])
    )
    forbidden = sorted(
        path
        for path in paths
        if any(path_matches(path, pattern) for pattern in contract["forbidden_paths"])
    )
    return {"outside_allowed_paths": outside, "forbidden_paths_changed": forbidden}


def parse_cli_claim(raw: str) -> tuple[str, str]:
    claim, separator, command = raw.partition(":")
    if not separator or not claim.strip() or not command.strip():
        raise ValueError("--verify-claim must use CLAIM:COMMAND")
    if len(command) > MAX_COMMAND_CHARS:
        raise ValueError(f"verification command exceeds {MAX_COMMAND_CHARS} characters")
    return CLAIM_ALIASES.get(claim.strip(), claim.strip()), command.strip()


def claimed_commands(
    contract: dict[str, Any] | None, cli_claims: list[tuple[str, str]]
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    if contract is not None:
        commands = contract["verification_commands"]
        for claim, references in contract["verification_claims"].items():
            result.setdefault(claim, set()).update(commands[item] for item in references)
    for claim, command in cli_claims:
        result.setdefault(claim, set()).add(command)
    return result


def structured_contract_claimed_commands(
    contract: dict[str, Any] | None,
) -> dict[str, set[str]]:
    """Return only structured claims originating in the loaded contract."""

    result: dict[str, set[str]] = {}
    if contract is None:
        return result
    commands = contract["verification_commands"]
    for claim, bindings in contract["verification_claim_bindings"].items():
        for binding in bindings:
            result.setdefault(claim, set()).update(
                commands[command_id] for command_id in binding["command_ids"]
            )
    return result


def verification_coverage(
    required_behaviors: list[dict[str, str]],
    claims: dict[str, set[str]],
    passed_commands: set[str],
    *,
    tier: int,
) -> tuple[str, dict[str, Any]]:
    required = [item["id"] for item in required_behaviors]
    if tier == 0:
        coverage = "complete" if passed_commands else "unverified"
        return coverage, {
            "required": required,
            "covered": required if coverage == "complete" else [],
            "missing": [] if coverage == "complete" else required,
            "claims": {},
        }
    covered = sorted(
        behavior
        for behavior in required
        if claims.get(behavior, set()) & passed_commands
    )
    missing = sorted(set(required) - set(covered))
    coverage = "complete" if not missing else "partial" if covered else "unverified"
    return coverage, {
        "required": required,
        "covered": covered,
        "missing": missing,
        "claims": {key: sorted(value) for key, value in sorted(claims.items())},
    }
