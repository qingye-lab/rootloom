#!/usr/bin/env python3
"""Manage Rootloom's small, repository-owned engineering memory."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any


PLUGIN_LIB = Path(__file__).resolve().parents[3] / "lib"
sys.path.insert(0, str(PLUGIN_LIB))
import rootloom_memory as memory_contract
from rootloom_lock import LockBusyError, LockFileError, simple_lock
from rootloom_paths import normalize_repo_path


MEMORY_DIR = ".project-memory"
FILES = memory_contract.MEMORY_FILES
FORMAT = memory_contract.MEMORY_FORMAT
CONTEXT_FORMAT = "rootloom-project-context-v1"
STATUSES = memory_contract.MEMORY_STATUSES
MAX_COLLECTION_BYTES = memory_contract.MAX_COLLECTION_BYTES
MAX_ARCHITECTURE_BYTES = memory_contract.MAX_ARCHITECTURE_BYTES
MAX_ENTRIES = memory_contract.MAX_ENTRIES
DEFAULT_CONTEXT_LIMIT = 20
MEMORY_LOCK_TIMEOUT_SECONDS = 5.0


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


def memory_root(repo: Path) -> Path:
    resolved = repo.expanduser().resolve()
    if not (resolved / ".git").exists():
        raise ValueError(f"not a Git repository: {resolved}")
    root = resolved / MEMORY_DIR
    if root.is_symlink():
        raise ValueError(f"project-memory directory must not be a symlink: {root}")
    return root


def bounded_text(path: Path, limit: int) -> tuple[str, bool]:
    return memory_contract.bounded_text(path, limit, allow_truncate=True)


def default_collection(kind: str) -> dict[str, Any]:
    return memory_contract.default_collection(kind)


def parse_iso_date(value: Any, *, field: str, path: Path | None = None) -> date:
    return memory_contract.parse_iso_date(value, field=field, path=path)


def normalize_path(raw: str) -> str:
    return normalize_repo_path(raw, label="memory path")


def clean_text(value: str, *, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


def normalized_strings(values: list[str], *, field: str) -> list[str]:
    return sorted({clean_text(value, field=field) for value in values})


def validate_entry(kind: str, entry: Any, *, path: Path) -> dict[str, Any]:
    return memory_contract.validate_entry(kind, entry, path=path)


def load_collection(root: Path, kind: str) -> dict[str, Any]:
    return memory_contract.load_collection(root, kind)


def save_collection(root: Path, kind: str, payload: dict[str, Any]) -> None:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    if len(encoded) > MAX_COLLECTION_BYTES:
        raise ValueError(f"project-memory file would exceed {MAX_COLLECTION_BYTES} bytes")
    atomic_write(root / FILES[kind], encoded)


@contextmanager
def memory_lock(root: Path):
    if root.is_symlink():
        raise ValueError(f"project-memory directory must not be a symlink: {root}")
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / "memory.lock"
    deadline = time.monotonic() + MEMORY_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            with simple_lock(lock_path):
                yield
                return
        except LockBusyError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"project-memory lock remained busy: {lock_path}") from exc
            time.sleep(0.025)
        except LockFileError as exc:
            raise ValueError(f"project-memory lock could not be used: {exc}") from exc


def _initialize_unlocked(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    architecture = root / "architecture.md"
    if architecture.is_symlink():
        raise ValueError(f"project-memory files must not be symlinks: {architecture}")
    if not architecture.exists():
        atomic_write(
            architecture,
            (
                "# Project architecture\n\n"
                "Record stable module ownership, dependency direction, and invariants here. "
                "Link each rule to current source, tests, or an accepted decision record.\n"
            ).encode("utf-8"),
        )
    readme = root / "README.md"
    if readme.is_symlink():
        raise ValueError(f"project-memory files must not be symlinks: {readme}")
    if not readme.exists():
        atomic_write(
            readme,
            (
                "# Engineering memory\n\n"
                "Reviewable architecture, risk, decision, and failure knowledge for future "
                "engineering tasks. Memory is advisory; current repository evidence wins. "
                "Updates are always explicit.\n"
            ).encode("utf-8"),
        )
    for kind in FILES:
        path = root / FILES[kind]
        if path.is_symlink():
            raise ValueError(f"project-memory files must not be symlinks: {path}")
        if not path.exists():
            save_collection(root, kind, default_collection(kind))


def initialize(root: Path) -> None:
    with memory_lock(root):
        _initialize_unlocked(root)


def entry_identity(kind: str, entry: dict[str, Any]) -> str:
    return memory_contract.entry_identity(kind, entry)


def append_entry(root: Path, kind: str, entry: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    with memory_lock(root):
        _initialize_unlocked(root)
        payload = load_collection(root, kind)
        entry["id"] = entry_identity(kind, entry)
        for existing in payload["entries"]:
            if existing.get("id", entry_identity(kind, existing)) == entry["id"]:
                return existing, True
        if len(payload["entries"]) >= MAX_ENTRIES:
            raise ValueError(f"project-memory entries exceed {MAX_ENTRIES}")
        payload["entries"].append(entry)
        save_collection(root, kind, payload)
        return entry, False


def words(value: str) -> set[str]:
    return memory_contract.words(value)


def path_score(candidate: str, requested: str) -> int:
    return memory_contract.path_score(candidate, requested)


def relevance(kind: str, entry: dict[str, Any], paths: list[str], query_terms: set[str]) -> int:
    return memory_contract.relevance(kind, entry, paths, query_terms)


def stale_reason(entry: dict[str, Any], today: date) -> str | None:
    return memory_contract.stale_reason(entry, today)


def context_payload(
    root: Path,
    *,
    paths: list[str],
    query: str,
    limit: int,
    include_stale: bool,
    today: date | None = None,
) -> dict[str, Any]:
    if limit <= 0 or limit > 100:
        raise ValueError("context limit must be between 1 and 100")
    today = today or date.today()
    normalized_paths = sorted({normalize_path(path) for path in paths})
    query_terms = words(query)
    architecture, architecture_truncated = bounded_text(
        root / "architecture.md", MAX_ARCHITECTURE_BYTES
    )
    result: dict[str, Any] = {
        "format": CONTEXT_FORMAT,
        "architecture": architecture,
        "selection": {
            "paths": normalized_paths,
            "query": query,
            "limit_per_kind": limit,
            "include_stale": include_stale,
            "truncated": {},
        },
        "stale": {kind: [] for kind in FILES},
        "warnings": (["architecture.md truncated"] if architecture_truncated else []),
    }
    for kind in FILES:
        ranked: list[tuple[int, str, str, dict[str, Any]]] = []
        stale: list[tuple[int, str, dict[str, Any]]] = []
        for raw in load_collection(root, kind)["entries"]:
            score = relevance(kind, raw, normalized_paths, query_terms)
            if score <= 0:
                continue
            entry = dict(raw)
            entry.setdefault("id", entry_identity(kind, entry))
            entry.setdefault("status", "active")
            reason = stale_reason(entry, today)
            if reason:
                stale.append((score, entry["id"], {"id": entry["id"], "summary": entry["summary"], "reason": reason}))
                if not include_stale:
                    continue
            ranked.append((score, entry.get("date", ""), entry["id"], entry))
        ranked.sort(key=lambda item: item[2])
        ranked.sort(key=lambda item: item[1], reverse=True)
        ranked.sort(key=lambda item: item[0], reverse=True)
        stale.sort(key=lambda item: (-item[0], item[1]))
        result[kind] = [entry for _score, _date, _id, entry in ranked[:limit]]
        result["stale"][kind] = [entry for _score, _id, entry in stale[:limit]]
        result["selection"]["truncated"][kind] = len(ranked) > limit
    return result


def set_status(
    root: Path,
    *,
    kind: str,
    entry_id: str,
    status: str,
    superseded_by: str | None,
) -> dict[str, Any]:
    if status == "superseded" and not superseded_by:
        raise ValueError("superseded status requires --superseded-by")
    if status != "superseded" and superseded_by:
        raise ValueError("--superseded-by is valid only with superseded status")
    with memory_lock(root):
        payload = load_collection(root, kind)
        for entry in payload["entries"]:
            existing_id = entry.get("id", entry_identity(kind, entry))
            if existing_id != entry_id:
                continue
            entry["id"] = existing_id
            entry["status"] = status
            entry["updated"] = date.today().isoformat()
            if superseded_by:
                entry["superseded_by"] = superseded_by
            else:
                entry.pop("superseded_by", None)
            save_collection(root, kind, payload)
            return entry
        raise ValueError(f"project-memory entry not found: {kind}/{entry_id}")


def add_record_options(parser: argparse.ArgumentParser, *, paths: bool = True) -> None:
    if paths:
        parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--expires")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")

    context = commands.add_parser("context")
    context.add_argument("--path", action="append", default=[])
    context.add_argument("--query", default="")
    context.add_argument("--limit", type=int, default=DEFAULT_CONTEXT_LIMIT)
    context.add_argument("--include-stale", action="store_true")

    failure = commands.add_parser("record-failure")
    failure.add_argument("--summary", required=True)
    failure.add_argument("--root-cause", required=True)
    failure.add_argument("--fix", required=True)
    add_record_options(failure)

    risk = commands.add_parser("record-risk")
    risk.add_argument("--summary", required=True)
    risk.add_argument("--mitigation", required=True)
    add_record_options(risk)

    decision = commands.add_parser("record-decision")
    decision.add_argument("--summary", required=True)
    decision.add_argument("--record", required=True)
    add_record_options(decision)

    status = commands.add_parser("set-status")
    status.add_argument("--kind", choices=tuple(FILES), required=True)
    status.add_argument("--id", required=True)
    status.add_argument("--status", choices=STATUSES, required=True)
    status.add_argument("--superseded-by")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = memory_root(args.repo)
    if args.command == "init":
        initialize(root)
        print(root)
        return 0
    if args.command == "context":
        payload = context_payload(
            root,
            paths=args.path,
            query=args.query,
            limit=args.limit,
            include_stale=args.include_stale,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "set-status":
        entry = set_status(
            root,
            kind=args.kind,
            entry_id=args.id,
            status=args.status,
            superseded_by=args.superseded_by,
        )
        print(json.dumps(entry, ensure_ascii=False, sort_keys=True))
        return 0

    expires = args.expires
    if expires:
        parsed_expiry = parse_iso_date(expires, field="expires")
        if parsed_expiry < date.today():
            raise ValueError("new project-memory entries cannot already be expired")
    common = {
        "date": date.today().isoformat(),
        "status": "active",
        "evidence": normalized_strings(args.evidence, field="evidence"),
        "paths": sorted({normalize_path(path) for path in args.path}),
    }
    if expires:
        common["expires"] = expires
    if args.command == "record-failure":
        kind = "failures"
        entry = {
            **common,
            "summary": clean_text(args.summary, field="summary"),
            "root_cause": clean_text(args.root_cause, field="root-cause"),
            "fix": clean_text(args.fix, field="fix"),
        }
    elif args.command == "record-risk":
        kind = "risks"
        entry = {
            **common,
            "summary": clean_text(args.summary, field="summary"),
            "mitigation": clean_text(args.mitigation, field="mitigation"),
        }
    else:
        kind = "decisions"
        entry = {
            **common,
            "summary": clean_text(args.summary, field="summary"),
            "record": clean_text(args.record, field="record"),
        }
    stored, deduplicated = append_entry(root, kind, entry)
    result = dict(stored)
    result["deduplicated"] = deduplicated
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
