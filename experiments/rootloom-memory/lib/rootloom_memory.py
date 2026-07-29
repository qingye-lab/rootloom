"""Strict shared read contract for Rootloom engineering memory v1."""

from __future__ import annotations

from datetime import date
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import re
from typing import Any

from rootloom_paths import normalize_repo_path


MEMORY_FORMAT = "rootloom-project-memory-v1"
MEMORY_FILES = {
    "failures": "failures.json",
    "risks": "known-risks.json",
    "decisions": "decisions.json",
}
MEMORY_STATUSES = ("active", "resolved", "superseded")
MAX_COLLECTION_BYTES = 1024 * 1024
MAX_ARCHITECTURE_BYTES = 64 * 1024
MAX_ENTRIES = 1000
TOKEN = re.compile(r"[\w.-]+", re.UNICODE)
IDENTITY_FIELDS = {
    "failures": ("summary", "root_cause", "fix", "paths", "evidence", "expires"),
    "risks": ("summary", "mitigation", "paths", "evidence", "expires"),
    "decisions": ("summary", "record", "paths", "evidence", "expires"),
}
REQUIRED_FIELDS = {
    "failures": ("summary", "root_cause", "fix"),
    "risks": ("summary", "mitigation"),
    "decisions": ("summary", "record"),
}


def parse_iso_date(value: Any, *, field: str, path: Path | None = None) -> date:
    suffix = f": {path}" if path else ""
    if not isinstance(value, str):
        raise ValueError(f"project-memory {field} must be an ISO date{suffix}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"project-memory {field} must be an ISO date{suffix}") from exc


def normalize_memory_path(raw: str) -> str:
    return normalize_repo_path(raw, label="memory path")


def default_collection(kind: str) -> dict[str, Any]:
    if kind not in MEMORY_FILES:
        raise ValueError(f"unsupported project-memory kind: {kind}")
    return {"format": MEMORY_FORMAT, "kind": kind, "entries": []}


def entry_identity(kind: str, entry: dict[str, Any]) -> str:
    identity = {
        field: entry.get(field, [] if field in {"paths", "evidence"} else "")
        for field in IDENTITY_FIELDS[kind]
    }
    digest = hashlib.sha256(
        json.dumps(
            identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"{kind[:-1]}-{digest}"


def validate_entry(kind: str, entry: Any, *, path: Path) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError(f"project-memory entries must be objects: {path}")
    for field in REQUIRED_FIELDS[kind]:
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            raise ValueError(
                f"project-memory {kind}.{field} must be a nonempty string: {path}"
            )
    if "date" in entry:
        parse_iso_date(entry["date"], field="date", path=path)
    if "expires" in entry:
        parse_iso_date(entry["expires"], field="expires", path=path)
    if entry.get("status", "active") not in MEMORY_STATUSES:
        raise ValueError(
            f"project-memory status must be one of {', '.join(MEMORY_STATUSES)}: {path}"
        )
    for field in ("paths", "evidence"):
        values = entry.get(field, [])
        if not isinstance(values, list) or any(
            not isinstance(value, str) for value in values
        ):
            raise ValueError(f"project-memory {field} must be a string list: {path}")
        if field == "paths" and "id" in entry:
            for value in values:
                normalize_memory_path(value)
    if "id" in entry and (
        not isinstance(entry["id"], str) or not entry["id"].strip()
    ):
        raise ValueError(f"project-memory id must be a nonempty string: {path}")
    return entry


def _descriptor_identity(info: os.stat_result) -> tuple[int, int, int]:
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def bounded_read(path: Path, limit: int, *, allow_truncate: bool = False) -> tuple[bytes, bool]:
    """Read through one no-follow descriptor and verify stable identity/size."""

    if limit <= 0:
        raise ValueError("bounded read limit must be positive")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        before = path.lstat()
    except FileNotFoundError:
        return b"", False
    if stat.S_ISLNK(before.st_mode):
        raise ValueError(f"project-memory files must not be symlinks: {path}")
    try:
        descriptor = os.open(path, flags | nofollow)
    except OSError as exc:
        raise ValueError(f"could not open project-memory file: {path}: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _descriptor_identity(opened) != _descriptor_identity(before):
            raise ValueError(f"project-memory file identity changed before read: {path}")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
        if (
            _descriptor_identity(after) != _descriptor_identity(opened)
            or after.st_size != opened.st_size
        ):
            raise ValueError(f"project-memory file changed during read: {path}")
        raw = b"".join(chunks)
        truncated = len(raw) > limit or after.st_size > limit
        if truncated and not allow_truncate:
            raise ValueError(f"project-memory file exceeds {limit} bytes: {path}")
        return raw[:limit], truncated
    finally:
        os.close(descriptor)


def bounded_text(path: Path, limit: int, *, allow_truncate: bool = False) -> tuple[str, bool]:
    raw, truncated = bounded_read(path, limit, allow_truncate=allow_truncate)
    try:
        return raw.decode("utf-8", errors="replace" if truncated else "strict"), truncated
    except UnicodeDecodeError as exc:
        raise ValueError(f"project-memory file is not UTF-8: {path}") from exc


def load_collection(root: Path, kind: str) -> dict[str, Any]:
    path = root / MEMORY_FILES[kind]
    if not path.exists() and not path.is_symlink():
        return default_collection(kind)
    raw, _truncated = bounded_text(path, MAX_COLLECTION_BYTES)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid project-memory JSON: {path}") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("format") != MEMORY_FORMAT
        or payload.get("kind") != kind
    ):
        raise ValueError(f"unsupported project-memory file: {path}")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"project-memory entries must be a list: {path}")
    if len(entries) > MAX_ENTRIES:
        raise ValueError(f"project-memory entries exceed {MAX_ENTRIES}: {path}")
    for entry in entries:
        validate_entry(kind, entry, path=path)
    return payload


def words(value: str) -> set[str]:
    return {token.lower() for token in TOKEN.findall(value) if len(token) > 1}


def path_score(candidate: str, requested: str) -> int:
    try:
        candidate = normalize_memory_path(candidate)
        requested = normalize_memory_path(requested)
    except ValueError:
        return 0
    if candidate == requested:
        return 100
    candidate_path = PurePosixPath(candidate)
    requested_path = PurePosixPath(requested)
    if candidate_path in requested_path.parents or requested_path in candidate_path.parents:
        return 60
    if candidate_path.name == requested_path.name:
        return 30
    return 0


def relevance(
    kind: str,
    entry: dict[str, Any],
    paths: list[str],
    query_terms: set[str],
) -> int:
    if not paths and not query_terms:
        return 1
    score = 0
    for candidate in entry.get("paths", []):
        for requested in paths:
            score = max(score, path_score(candidate, requested))
    searchable = " ".join(
        str(entry.get(field, ""))
        for field in (*REQUIRED_FIELDS[kind], "paths", "evidence")
    )
    score += 5 * len(query_terms & words(searchable))
    return score


def stale_reason(entry: dict[str, Any], today: date) -> str | None:
    status = entry.get("status", "active")
    if status != "active":
        return str(status)
    expires = entry.get("expires")
    if expires and parse_iso_date(expires, field="expires") < today:
        return f"expired:{expires}"
    return None
