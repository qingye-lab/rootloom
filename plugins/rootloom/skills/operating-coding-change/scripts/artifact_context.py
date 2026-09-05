#!/usr/bin/env python3
"""Prepare and validate bounded receipts for out-of-context artifact analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any, NoReturn


MANIFEST_FORMAT = "rootloom-artifact-manifest-v1"
PREPARE_FORMAT = "rootloom-artifact-prepare-v1"
RECEIPT_FORMAT = "rootloom-artifact-context-v1"
MAX_ARTIFACTS = 16
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_INTENT_BYTES = 2 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_RECEIPT_BYTES = 24 * 1024
MAX_SUMMARY_CHARS = 4_000
MAX_NOTE_CHARS = 2_000
MAX_FACTS = 12
MAX_FACT_CHARS = 800
MAX_EVIDENCE_ITEMS = 4
MAX_EVIDENCE_CHARS = 500
MAX_UNCERTAINTIES = 8
MAX_HINTS = 12
MAX_LIST_ITEM_CHARS = 500


class ArtifactContextError(ValueError):
    """Raised when an artifact bundle or receipt violates the lane contract."""


def fail(message: str) -> NoReturn:
    raise ArtifactContextError(message)


def canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def private_directory(path: Path) -> None:
    if path.is_symlink():
        fail(f"cache directory must not be a symlink: {path}")
    existed = path.exists()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        fail(f"cache directory must be a real directory: {path}")
    if not existed:
        try:
            path.chmod(0o700)
        except OSError as exc:
            if os.name == "posix":
                fail(f"cannot secure cache directory {path}: {exc}")
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        fail(f"cache directory permissions are not private: {path}")


def atomic_write(path: Path, payload: bytes) -> None:
    private_directory(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError as exc:
            if os.name == "posix":
                fail(f"cannot secure cache file {path}: {exc}")
        if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            fail(f"cache file permissions are not private: {path}")
    finally:
        if temporary.exists():
            temporary.unlink()


def resolve_cache_root(value: str | None) -> Path:
    if value:
        root = Path(value).expanduser()
    elif os.environ.get("ROOTLOOM_ARTIFACT_CACHE"):
        root = Path(os.environ["ROOTLOOM_ARTIFACT_CACHE"]).expanduser()
    else:
        codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
        root = codex_home / ".rootloom" / "artifact-context"
    if not root.is_absolute():
        root = Path.cwd() / root
    private_directory(root)
    return root.resolve()


def open_regular_file(path: Path) -> tuple[int, os.stat_result]:
    if path.is_symlink():
        fail(f"artifact must not be a symlink: {path}")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        fail(f"cannot open artifact {path}: {exc}")
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        fail(f"artifact must be a regular file: {path}")
    return descriptor, metadata


def inspect_artifact(raw_path: str) -> dict[str, Any]:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.absolute()
    descriptor, before = open_regular_file(path)
    try:
        if before.st_size > MAX_ARTIFACT_BYTES:
            fail(f"artifact exceeds {MAX_ARTIFACT_BYTES} bytes: {path}")
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
            after = os.fstat(handle.fileno())
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        fail(f"artifact changed while hashing: {path}")
    try:
        current = path.lstat()
    except OSError as exc:
        fail(f"artifact disappeared while hashing {path}: {exc}")
    if stat.S_ISLNK(current.st_mode) or (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ):
        fail(f"artifact path changed while hashing: {path}")
    media_type = mimetypes.guess_type(path.name, strict=False)[0] or "application/octet-stream"
    return {
        "bytes": before.st_size,
        "media_type": media_type,
        "name": path.name,
        "sha256": digest.hexdigest(),
        "source_path": str(path),
    }


def bundle_directory(cache_root: Path, bundle_id: str) -> Path:
    if len(bundle_id) != 64 or any(character not in "0123456789abcdef" for character in bundle_id):
        fail("bundle id must be a lowercase SHA-256 digest")
    shard = cache_root / bundle_id[:2]
    private_directory(shard)
    bundle = shard / bundle_id
    private_directory(bundle)
    return bundle


def read_json_file(path: Path, maximum_bytes: int, label: str) -> dict[str, Any]:
    descriptor, metadata = open_regular_file(path)
    if metadata.st_nlink != 1:
        os.close(descriptor)
        fail(f"{label} must not be hard-linked: {path}")
    if metadata.st_size > maximum_bytes:
        os.close(descriptor)
        fail(f"{label} exceeds {maximum_bytes} bytes")
    with os.fdopen(descriptor, "rb") as handle:
        payload = handle.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        fail(f"{label} exceeds {maximum_bytes} bytes")
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"{label} is not valid UTF-8 JSON: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def validate_string(value: object, label: str, maximum_chars: int, *, required: bool = True) -> str:
    if not isinstance(value, str):
        fail(f"{label} must be a string")
    normalized = value.strip()
    if required and not normalized:
        fail(f"{label} must not be empty")
    if len(normalized) > maximum_chars:
        fail(f"{label} exceeds {maximum_chars} characters")
    lowered = normalized.lower()
    if "data:image/" in lowered or "data:audio/" in lowered or "data:video/" in lowered or ";base64," in lowered:
        fail(f"{label} must not embed raw artifact data")
    if "\x00" in normalized:
        fail(f"{label} must not contain NUL")
    return normalized


def exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        fail(f"{label} fields must be exactly: {', '.join(sorted(expected))}")


def validate_string_list(
    value: object, label: str, maximum_items: int, maximum_chars: int
) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum_items:
        fail(f"{label} must be an array with at most {maximum_items} items")
    return [validate_string(item, f"{label}[{index}]", maximum_chars) for index, item in enumerate(value)]


def validate_manifest(value: dict[str, Any], bundle_id: str) -> dict[str, Any]:
    exact_keys(value, {"artifacts", "bundle_id", "format", "intent"}, "manifest")
    if value["format"] != MANIFEST_FORMAT or value["bundle_id"] != bundle_id:
        fail("manifest identity does not match its bundle")
    intent = validate_string(value["intent"], "manifest.intent", MAX_INTENT_BYTES)
    if len(intent.encode("utf-8")) > MAX_INTENT_BYTES:
        fail(f"manifest.intent exceeds {MAX_INTENT_BYTES} UTF-8 bytes")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= MAX_ARTIFACTS:
        fail(f"manifest.artifacts must contain 1-{MAX_ARTIFACTS} entries")
    required = {"bytes", "media_type", "name", "sha256", "source_path"}
    seen: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            fail(f"manifest.artifacts[{index}] must be an object")
        exact_keys(artifact, required, f"manifest.artifacts[{index}]")
        digest = validate_string(artifact["sha256"], f"manifest.artifacts[{index}].sha256", 64)
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            fail(f"manifest.artifacts[{index}].sha256 is invalid")
        if digest in seen:
            fail("manifest contains duplicate artifact digests")
        seen.add(digest)
        if not isinstance(artifact["bytes"], int) or not 0 <= artifact["bytes"] <= MAX_ARTIFACT_BYTES:
            fail(f"manifest.artifacts[{index}].bytes is invalid")
        validate_string(artifact["media_type"], f"manifest.artifacts[{index}].media_type", 255)
        validate_string(artifact["name"], f"manifest.artifacts[{index}].name", 255)
        source = validate_string(artifact["source_path"], f"manifest.artifacts[{index}].source_path", 4096)
        if not Path(source).is_absolute():
            fail(f"manifest.artifacts[{index}].source_path must be absolute")
    identity = {
        "artifacts": [
            {key: artifact[key] for key in ("bytes", "media_type", "sha256")} for artifact in artifacts
        ],
        "format": MANIFEST_FORMAT,
        "intent": value["intent"],
    }
    if hashlib.sha256(canonical_json_bytes(identity)).hexdigest() != bundle_id:
        fail("manifest content identity does not match its bundle")
    return value


def validate_receipt(value: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    exact_keys(
        value,
        {"artifact_notes", "bundle_id", "facts", "format", "retrieval_hints", "summary", "uncertainties"},
        "receipt",
    )
    if value["format"] != RECEIPT_FORMAT or value["bundle_id"] != manifest["bundle_id"]:
        fail("receipt identity does not match its bundle")
    summary = validate_string(value["summary"], "receipt.summary", MAX_SUMMARY_CHARS)
    expected_digests = {artifact["sha256"] for artifact in manifest["artifacts"]}
    notes = value["artifact_notes"]
    if not isinstance(notes, list) or len(notes) != len(expected_digests):
        fail("receipt.artifact_notes must contain exactly one note per artifact")
    normalized_notes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, note in enumerate(notes):
        if not isinstance(note, dict):
            fail(f"receipt.artifact_notes[{index}] must be an object")
        exact_keys(note, {"locators", "sha256", "summary"}, f"receipt.artifact_notes[{index}]")
        digest = validate_string(note["sha256"], f"receipt.artifact_notes[{index}].sha256", 64)
        if digest not in expected_digests or digest in seen:
            fail(f"receipt.artifact_notes[{index}].sha256 is missing or duplicated")
        seen.add(digest)
        normalized_notes.append(
            {
                "locators": validate_string_list(
                    note["locators"], f"receipt.artifact_notes[{index}].locators", MAX_HINTS, MAX_LIST_ITEM_CHARS
                ),
                "sha256": digest,
                "summary": validate_string(note["summary"], f"receipt.artifact_notes[{index}].summary", MAX_NOTE_CHARS),
            }
        )
    facts = value["facts"]
    if not isinstance(facts, list) or len(facts) > MAX_FACTS:
        fail(f"receipt.facts must contain at most {MAX_FACTS} items")
    normalized_facts: list[dict[str, Any]] = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            fail(f"receipt.facts[{index}] must be an object")
        exact_keys(fact, {"claim", "evidence"}, f"receipt.facts[{index}]")
        normalized_facts.append(
            {
                "claim": validate_string(fact["claim"], f"receipt.facts[{index}].claim", MAX_FACT_CHARS),
                "evidence": validate_string_list(
                    fact["evidence"], f"receipt.facts[{index}].evidence", MAX_EVIDENCE_ITEMS, MAX_EVIDENCE_CHARS
                ),
            }
        )
    normalized = {
        "artifact_notes": normalized_notes,
        "bundle_id": manifest["bundle_id"],
        "facts": normalized_facts,
        "format": RECEIPT_FORMAT,
        "retrieval_hints": validate_string_list(
            value["retrieval_hints"], "receipt.retrieval_hints", MAX_HINTS, MAX_LIST_ITEM_CHARS
        ),
        "summary": summary,
        "uncertainties": validate_string_list(
            value["uncertainties"], "receipt.uncertainties", MAX_UNCERTAINTIES, MAX_LIST_ITEM_CHARS
        ),
    }
    if len(canonical_json_bytes(normalized)) > MAX_RECEIPT_BYTES:
        fail(f"canonical receipt exceeds {MAX_RECEIPT_BYTES} bytes")
    return normalized


def load_bundle(cache_root: Path, bundle_id: str) -> tuple[Path, dict[str, Any]]:
    bundle = bundle_directory(cache_root, bundle_id)
    manifest = validate_manifest(
        read_json_file(bundle / "manifest.json", MAX_MANIFEST_BYTES, "manifest"), bundle_id
    )
    return bundle, manifest


def receipt_if_valid(bundle: Path, manifest: dict[str, Any]) -> dict[str, Any] | None:
    receipt_path = bundle / "receipt.json"
    if not receipt_path.exists():
        return None
    return validate_receipt(read_json_file(receipt_path, MAX_RECEIPT_BYTES, "receipt"), manifest)


def command_prepare(args: argparse.Namespace, cache_root: Path) -> dict[str, Any]:
    intent = validate_string(args.intent, "intent", MAX_INTENT_BYTES)
    if len(intent.encode("utf-8")) > MAX_INTENT_BYTES:
        fail(f"intent exceeds {MAX_INTENT_BYTES} UTF-8 bytes")
    if not 1 <= len(args.path) <= MAX_ARTIFACTS:
        fail(f"prepare accepts 1-{MAX_ARTIFACTS} paths")
    artifacts_by_digest: dict[str, dict[str, Any]] = {}
    total_bytes = 0
    for raw_path in args.path:
        artifact = inspect_artifact(raw_path)
        existing = artifacts_by_digest.get(artifact["sha256"])
        if existing is not None and existing["media_type"] != artifact["media_type"]:
            fail(
                "identical artifact bytes have conflicting inferred media types: "
                f"{existing['name']} and {artifact['name']}"
            )
        if existing is None:
            total_bytes += artifact["bytes"]
            if total_bytes > MAX_TOTAL_BYTES:
                fail(f"artifact bundle exceeds {MAX_TOTAL_BYTES} bytes")
            artifacts_by_digest[artifact["sha256"]] = artifact
    artifacts = sorted(artifacts_by_digest.values(), key=lambda item: item["sha256"])
    identity = {
        "artifacts": [
            {key: artifact[key] for key in ("bytes", "media_type", "sha256")} for artifact in artifacts
        ],
        "format": MANIFEST_FORMAT,
        "intent": intent,
    }
    bundle_id = hashlib.sha256(canonical_json_bytes(identity)).hexdigest()
    bundle = bundle_directory(cache_root, bundle_id)
    manifest = {
        "artifacts": artifacts,
        "bundle_id": bundle_id,
        "format": MANIFEST_FORMAT,
        "intent": intent,
    }
    validate_manifest(manifest, bundle_id)
    atomic_write(bundle / "manifest.json", canonical_json_bytes(manifest))
    cached = receipt_if_valid(bundle, manifest)
    result: dict[str, Any] = {
        "artifact_count": len(artifacts),
        "bundle_id": bundle_id,
        "format": PREPARE_FORMAT,
        "manifest_path": str(bundle / "manifest.json"),
        "receipt_path": str(bundle / "receipt.json"),
        "status": "cached" if cached is not None else "needs-analysis",
        "total_bytes": total_bytes,
    }
    if cached is None:
        descriptor, draft_name = tempfile.mkstemp(prefix="draft-", suffix=".json", dir=bundle)
        template = {
            "artifact_notes": [
                {"locators": [], "sha256": artifact["sha256"], "summary": ""} for artifact in artifacts
            ],
            "bundle_id": bundle_id,
            "facts": [{"claim": "", "evidence": []}],
            "format": RECEIPT_FORMAT,
            "retrieval_hints": [],
            "summary": "",
            "uncertainties": [],
        }
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(template))
        os.chmod(draft_name, 0o600)
        result["draft_path"] = draft_name
    return result


def command_finalize(args: argparse.Namespace, cache_root: Path) -> dict[str, Any]:
    bundle, manifest = load_bundle(cache_root, args.bundle_id)
    draft = Path(os.path.abspath(Path(args.draft).expanduser()))
    if draft.is_symlink() or draft.parent != bundle or not draft.name.startswith("draft-"):
        fail("draft must be a non-symlink draft file inside the selected bundle")
    receipt = validate_receipt(read_json_file(draft, MAX_RECEIPT_BYTES, "draft receipt"), manifest)
    for artifact in manifest["artifacts"]:
        current = inspect_artifact(artifact["source_path"])
        if current["sha256"] != artifact["sha256"] or current["bytes"] != artifact["bytes"]:
            fail(f"artifact changed after prepare: {artifact['source_path']}")
    atomic_write(bundle / "receipt.json", canonical_json_bytes(receipt))
    try:
        draft.unlink()
    except FileNotFoundError:
        pass
    return {
        "bundle_id": args.bundle_id,
        "format": PREPARE_FORMAT,
        "receipt_bytes": len(canonical_json_bytes(receipt)),
        "receipt_path": str(bundle / "receipt.json"),
        "status": "finalized",
    }


def command_show(args: argparse.Namespace, cache_root: Path) -> dict[str, Any]:
    bundle, manifest = load_bundle(cache_root, args.bundle_id)
    receipt = receipt_if_valid(bundle, manifest)
    if receipt is None:
        fail("bundle has no finalized receipt")
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--cache-root", help="Override the user-local artifact receipt cache")
    commands = result.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Hash files and locate or create a bounded receipt bundle")
    prepare.add_argument("--intent", required=True, help="Exact question the isolated worker must answer")
    prepare.add_argument("--path", action="append", required=True, help="Exact artifact path; repeat for a bundle")
    finalize = commands.add_parser("finalize", help="Validate an isolated worker draft and commit its receipt")
    finalize.add_argument("--bundle-id", required=True)
    finalize.add_argument("--draft", required=True)
    show = commands.add_parser("show", help="Print a finalized bounded receipt")
    show.add_argument("--bundle-id", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        cache_root = resolve_cache_root(args.cache_root)
        if args.command == "prepare":
            result = command_prepare(args, cache_root)
        elif args.command == "finalize":
            result = command_finalize(args, cache_root)
        else:
            result = command_show(args, cache_root)
    except ArtifactContextError as exc:
        print(f"artifact-context: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
