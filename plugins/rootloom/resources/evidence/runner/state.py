"""Bounded Git and worktree capture for Personal Core."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time
from typing import Any


PLUGIN_LIB = Path(__file__).resolve().parents[3] / "lib"
sys.path.insert(0, str(PLUGIN_LIB))
from rootloom_paths import (
    MAX_REVIEWABLE_PATHS,
    is_sensitive_material_path,
    normalize_repo_path,
    sensitive_material_git_pathspecs,
    validate_git_repo_path,
)

from .process import run_command


DEFAULT_MAX_GIT_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_GIT_SECONDS = 30.0
DEFAULT_MAX_CAPTURE_SECONDS = 90.0
DEFAULT_MAX_STATUS_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_STATUS_PATHS = 10_000
DEFAULT_MAX_SENSITIVE_PATHS = 10_000
DEFAULT_MAX_SENSITIVE_CANDIDATES = 50_000
DEFAULT_MAX_FINGERPRINT_FILE_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_FINGERPRINT_TOTAL_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_TEXT_PATCH_FILE_BYTES = 256 * 1024


class CaptureDeadline:
    """One monotonic budget shared by every phase of a repository capture."""

    def __init__(self, max_seconds: float) -> None:
        if not math.isfinite(max_seconds) or max_seconds <= 0:
            raise ValueError("capture time budget must be finite and positive")
        self.max_seconds = float(max_seconds)
        self.started_at = time.monotonic()

    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    def remaining_seconds(self) -> float:
        remaining = self.max_seconds - self.elapsed_seconds()
        if remaining <= 0:
            raise ValueError(
                "Repository capture exceeded configured "
                f"{self.max_seconds:g}-second aggregate budget"
            )
        return remaining

    def checkpoint(self) -> None:
        self.remaining_seconds()


def _git_result(
    repo: Path,
    *args: str,
    max_bytes: int,
    max_git_seconds: float,
    capture_deadline: CaptureDeadline | None = None,
) -> tuple[int, bytes]:
    if max_bytes <= 0:
        raise ValueError("Git capture budget must be positive")
    if not math.isfinite(max_git_seconds) or max_git_seconds <= 0:
        raise ValueError("Git time budget must be finite and positive")
    timeout = max_git_seconds
    deadline_limited = False
    if capture_deadline is not None:
        remaining = capture_deadline.remaining_seconds()
        deadline_limited = remaining < timeout
        timeout = min(timeout, remaining)
    result, output = run_command(
        ["git", "--no-pager", *args],
        cwd=repo,
        timeout=timeout,
        max_output_bytes=max_bytes,
        inherit_stdin=False,
    )
    command = "git " + " ".join(args)
    if result.timed_out:
        if deadline_limited:
            raise ValueError(
                "Repository capture exceeded configured "
                f"{capture_deadline.max_seconds:g}-second aggregate budget"
            )
        raise ValueError(
            f"Git command exceeded configured {max_git_seconds:g}-second budget: {command}"
        )
    if result.output_limit_exceeded:
        raise ValueError(
            f"{command} exceeds configured {max_bytes}-byte budget"
        )
    if not result.process_tree_converged:
        raise ValueError(f"Git process tree did not converge: {command}")
    if capture_deadline is not None:
        capture_deadline.checkpoint()
    return result.exit_code, output


def git_identity(
    repo: Path,
    *,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    capture_deadline: CaptureDeadline | None = None,
) -> dict[str, str]:
    """Return the commit/ref/index identity that bounds a worktree capture."""

    head_code, head_output = _git_result(
        repo,
        "rev-parse",
        "--verify",
        "--quiet",
        "HEAD",
        max_bytes=4096,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    if head_code == 0:
        head = head_output.decode("utf-8", errors="surrogateescape").strip()
    else:
        head = ""
    ref_code, ref_output = _git_result(
        repo,
        "symbolic-ref",
        "--quiet",
        "HEAD",
        max_bytes=4096,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    if ref_code == 0:
        head_ref = ref_output.decode("utf-8", errors="surrogateescape").strip()
    elif ref_code == 1 and head:
        head_ref = ""
    else:
        reason = (head_output if not head else ref_output).decode(
            "utf-8", errors="replace"
        ).strip()
        raise ValueError(f"git HEAD ref is invalid: {reason or 'symbolic ref failed'}")
    index_sha256 = git_bounded(
        repo,
        "write-tree",
        max_bytes=4096,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    ).decode("ascii").strip()
    return {"head": head, "head_ref": head_ref, "index_sha256": index_sha256}


def git_bounded(
    repo: Path,
    *args: str,
    max_bytes: int,
    accepted_codes: tuple[int, ...] = (0,),
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    capture_deadline: CaptureDeadline | None = None,
) -> bytes:
    returncode, output = _git_result(
        repo,
        *args,
        max_bytes=max_bytes,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    if returncode not in accepted_codes:
        reason = output.decode("utf-8", errors="replace").strip()
        raise ValueError(f"git {' '.join(args)} failed: {reason}")
    return output


def repository_changes(
    repo: Path,
    *,
    max_bytes: int = DEFAULT_MAX_STATUS_BYTES,
    max_paths: int = DEFAULT_MAX_STATUS_PATHS,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    capture_deadline: CaptureDeadline | None = None,
) -> tuple[list[dict[str, str]], list[str]]:
    raw = git_bounded(
        repo,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        max_bytes=max_bytes,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    records = raw.split(b"\0")
    changes: list[dict[str, str]] = []
    untracked: list[str] = []
    index = 0
    while index < len(records):
        if capture_deadline is not None:
            capture_deadline.checkpoint()
        record = records[index]
        index += 1
        if not record:
            continue
        decoded = record.decode("utf-8", errors="surrogateescape")
        status = decoded[:2]
        path = validate_git_repo_path(decoded[3:], label="Git status path")
        original = ""
        if "R" in status or "C" in status:
            if index >= len(records):
                raise ValueError("incomplete Git rename/copy status record")
            original = validate_git_repo_path(
                records[index].decode("utf-8", errors="surrogateescape"),
                label="Git status original path",
            )
            index += 1
        changes.append({"status": status, "path": path, "original_path": original})
        if len(changes) > max_paths:
            raise ValueError(f"Git status exceeds configured {max_paths}-path budget")
        if status == "??":
            untracked.append(path)
    return changes, untracked


def git_list_paths(
    repo: Path,
    args: list[str],
    *,
    max_bytes: int = DEFAULT_MAX_STATUS_BYTES,
    max_paths: int = DEFAULT_MAX_SENSITIVE_CANDIDATES,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    capture_deadline: CaptureDeadline | None = None,
) -> list[str]:
    raw = git_bounded(
        repo,
        *args,
        max_bytes=max_bytes,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    values: list[str] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        if capture_deadline is not None:
            capture_deadline.checkpoint()
        values.append(
            validate_git_repo_path(
                item.decode("utf-8", errors="surrogateescape"),
                label="Git listed path",
            )
        )
    if len(values) > max_paths:
        raise ValueError(f"Git path listing exceeds configured {max_paths}-path budget")
    return sorted(set(values))


def git_index_path_tags(
    repo: Path,
    pathspecs: list[str],
    *,
    max_bytes: int = DEFAULT_MAX_STATUS_BYTES,
    max_paths: int = DEFAULT_MAX_SENSITIVE_CANDIDATES,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    capture_deadline: CaptureDeadline | None = None,
) -> dict[str, set[str]]:
    """Return NUL-safe `git ls-files -v` tags for exact tracked candidates."""

    raw = git_bounded(
        repo,
        "ls-files",
        "-v",
        "-z",
        "--cached",
        "--",
        *pathspecs,
        max_bytes=max_bytes,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    tagged: dict[str, set[str]] = {}
    records = 0
    for item in raw.split(b"\0"):
        if not item:
            continue
        if capture_deadline is not None:
            capture_deadline.checkpoint()
        if len(item) < 3 or item[1:2] != b" ":
            raise ValueError("Git index path listing is malformed")
        try:
            tag = item[:1].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("Git index path tag is malformed") from exc
        path = validate_git_repo_path(
            item[2:].decode("utf-8", errors="surrogateescape"),
            label="Git indexed path",
        )
        tagged.setdefault(path, set()).add(tag)
        records += 1
        if records > max_paths:
            raise ValueError(
                f"Git index path listing exceeds configured {max_paths}-path budget"
            )
    return tagged


def discover_sensitive_paths(
    repo: Path,
    extra_sensitive: set[str],
    *,
    reviewable_paths: set[str] | None = None,
    max_sensitive_paths: int = DEFAULT_MAX_SENSITIVE_PATHS,
    max_candidate_paths: int = DEFAULT_MAX_SENSITIVE_CANDIDATES,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    capture_deadline: CaptureDeadline | None = None,
) -> list[str]:
    if max_sensitive_paths <= 0:
        raise ValueError("sensitive path budget must be positive")
    if len(extra_sensitive) > max_sensitive_paths:
        raise ValueError(
            "declared sensitive paths exceed configured "
            f"{max_sensitive_paths}-path budget"
        )
    if max_candidate_paths <= 0:
        raise ValueError("sensitive candidate path budget must be positive")
    # Ask Git only for paths that may match the shared policy, then reclassify
    # every result in Python. The built-in pathspecs are case-insensitive and a
    # literal directory pathspec recursively includes descendants, so ordinary
    # vendor/cache paths are not enumerated while sensitive-looking matches are
    # never silently excluded.
    pathspecs = [
        *sensitive_material_git_pathspecs(),
        *(f":(icase,literal){path}" for path in sorted(extra_sensitive)),
    ]
    tracked = git_list_paths(
        repo,
        ["ls-files", "-z", "--", *pathspecs],
        max_paths=max_candidate_paths,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    ignored = git_list_paths(
        repo,
        [
            "ls-files",
            "-z",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--",
            *pathspecs,
        ],
        max_paths=max_candidate_paths,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    candidates = set(tracked) | set(ignored)
    if len(candidates) > max_candidate_paths:
        raise ValueError(
            "sensitive candidate discovery exceeds configured "
            f"{max_candidate_paths}-path budget"
        )
    classified: set[str] = set()
    for path in candidates:
        if capture_deadline is not None:
            capture_deadline.checkpoint()
        if is_sensitive_material_path(
            path,
            extra_sensitive=extra_sensitive,
            reviewable_paths=reviewable_paths,
        ):
            classified.add(path)
    result = sorted(classified | set(extra_sensitive))
    if len(result) > max_sensitive_paths:
        raise ValueError(
            "sensitive path discovery exceeds configured "
            f"{max_sensitive_paths}-path budget"
        )
    return result


def _empty_tree(
    repo: Path,
    *,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    capture_deadline: CaptureDeadline | None = None,
) -> str:
    return git_bounded(
        repo,
        "hash-object",
        "-t",
        "tree",
        "--stdin",
        max_bytes=1024,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    ).decode("ascii").strip()


def tracked_patch(
    repo: Path,
    *,
    max_bytes: int = DEFAULT_MAX_GIT_BYTES,
    sensitive_paths: list[str] | None = None,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    capture_deadline: CaptureDeadline | None = None,
) -> bytes:
    head_code, head_output = _git_result(
        repo,
        "rev-parse",
        "--verify",
        "--quiet",
        "HEAD",
        max_bytes=4096,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    if head_code == 0:
        baseline = "HEAD"
    else:
        symbolic_code, _symbolic_output = _git_result(
            repo,
            "symbolic-ref",
            "--quiet",
            "HEAD",
            max_bytes=4096,
            max_git_seconds=max_git_seconds,
            capture_deadline=capture_deadline,
        )
        if symbolic_code != 0:
            reason = head_output.decode("utf-8", errors="replace").strip()
            raise ValueError(f"git HEAD is invalid: {reason or 'not an unborn branch'}")
        baseline = _empty_tree(
            repo,
            max_git_seconds=max_git_seconds,
            capture_deadline=capture_deadline,
        )
    exclusions = [f":(exclude,literal){path}" for path in sorted(sensitive_paths or [])]
    return git_bounded(
        repo,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--binary",
        baseline,
        "--",
        ".",
        *exclusions,
        max_bytes=max_bytes,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )


def _metadata_for_missing(path: str, *, sensitive: bool) -> dict[str, Any]:
    return {
        "path": path,
        "kind": "missing",
        "exists": False,
        "sensitive": sensitive,
        "content_read": False,
    }


def _lstat_repo_entry(repo: Path, path: str) -> os.stat_result | None:
    """Refuse repository paths that traverse a symlink or non-directory parent."""

    current = repo
    parts = PurePosixPath(path).parts
    for part in parts[:-1]:
        current /= part
        try:
            parent = current.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(parent.st_mode):
            raise ValueError(f"repository path traverses a symlink parent: {path}")
        if not stat.S_ISDIR(parent.st_mode):
            raise ValueError(f"repository path parent is not a directory: {path}")
    try:
        return (repo / path).lstat()
    except FileNotFoundError:
        return None


def _lstat_reviewable_entry(repo: Path, path: str) -> os.stat_result | None:
    """Preserve reviewability-specific parent diagnostics during Git resolution."""

    current = repo
    parts = PurePosixPath(path).parts
    for index, part in enumerate(parts):
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return None
        if index < len(parts) - 1 and stat.S_ISLNK(info.st_mode):
            component = current.relative_to(repo).as_posix()
            raise ValueError(
                "reviewable path parent component must not be a symlink: "
                + component
            )
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ValueError(
                f"reviewable path parent must be a directory: {path}"
            )
    return info


def canonical_reviewable_paths(
    repo: Path,
    paths: list[str] | set[str],
    *,
    allowed_missing: set[str] | None = None,
    max_paths: int = MAX_REVIEWABLE_PATHS,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    capture_deadline: CaptureDeadline | None = None,
) -> list[str]:
    """Resolve exact declarations to Git's spelling and refuse ignored files."""

    normalized = sorted(
        {normalize_repo_path(path, label="reviewable path") for path in paths}
    )
    if len(normalized) > max_paths:
        raise ValueError(
            f"reviewable paths exceed configured {max_paths}-path budget"
        )
    if not normalized:
        return []
    pathspecs = [f":(icase,literal){path}" for path in normalized]
    visible = git_list_paths(
        repo,
        [
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            *pathspecs,
        ],
        max_paths=max_paths,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    ignored = git_list_paths(
        repo,
        [
            "ls-files",
            "-z",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--",
            *pathspecs,
        ],
        max_paths=max_paths,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    index_tags = git_index_path_tags(
        repo,
        pathspecs,
        max_paths=max_paths,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    index_suppressed = {
        path
        for path, tags in index_tags.items()
        if any(tag.islower() or tag == "S" for tag in tags)
    }
    visible_set = set(visible)
    ignored_set = set(ignored)
    candidates = visible_set | ignored_set
    candidates_by_fold: dict[str, list[str]] = {}
    for candidate in sorted(candidates):
        if capture_deadline is not None:
            capture_deadline.checkpoint()
        candidates_by_fold.setdefault(candidate.casefold(), []).append(candidate)
    normalized_allowed_missing = {
        normalize_repo_path(path, label="allowed missing reviewable path")
        for path in allowed_missing or set()
    }
    canonical: list[str] = []
    for path in normalized:
        if capture_deadline is not None:
            capture_deadline.checkpoint()
        matches = candidates_by_fold.get(path.casefold(), [])
        if len(matches) > 1:
            raise ValueError(
                "reviewable path has case-insensitive repository ambiguity: "
                + path
            )
        if matches:
            actual = matches[0]
            if actual in index_suppressed:
                raise ValueError(
                    "reviewable path is hidden by Git index flags and cannot be "
                    "captured reliably: "
                    + actual
                )
            if actual in ignored_set and actual not in visible_set:
                raise ValueError(
                    "reviewable path is ignored and cannot be captured reliably: "
                    + actual
                )
            canonical.append(actual)
            continue
        info = _lstat_reviewable_entry(repo, path)
        if info is not None and not stat.S_ISREG(info.st_mode):
            raise ValueError(
                f"reviewable path must name a regular file: {path}"
            )
        if path in normalized_allowed_missing and info is None:
            canonical.append(path)
            continue
        if info is None:
            raise ValueError(
                f"reviewable path must name an existing regular file: {path}"
            )
        raise ValueError(
            "reviewable path is not Git-visible and cannot be captured reliably: "
            + path
        )
    folded = [path.casefold() for path in canonical]
    if len(folded) != len(set(folded)):
        raise ValueError(
            "reviewable paths resolve to case-insensitive repository duplicates"
        )
    return sorted(canonical)


def reviewable_path_metadata(
    repo: Path,
    paths: list[str] | set[str],
    *,
    capture_deadline: CaptureDeadline | None = None,
) -> list[dict[str, Any]]:
    """Capture bounded file identity while refusing aliases and type changes."""

    captured: list[dict[str, Any]] = []
    for path in sorted(
        {normalize_repo_path(path, label="reviewable path") for path in paths}
    ):
        if capture_deadline is not None:
            capture_deadline.checkpoint()
        info = _lstat_reviewable_entry(repo, path)
        if info is None:
            captured.append({"path": path, "kind": "missing", "exists": False})
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(
                "reviewable path must remain a regular file or be deleted: " + path
            )
        if info.st_nlink != 1:
            raise ValueError(
                f"reviewable path must have link count one: {path}"
            )
        captured.append(
            {
                "path": path,
                "kind": "file",
                "exists": True,
                "device": info.st_dev,
                "inode": info.st_ino,
                "link_count": info.st_nlink,
                "size": info.st_size,
                "mode": stat.S_IMODE(info.st_mode),
                "mtime_ns": info.st_mtime_ns,
                "ctime_ns": info.st_ctime_ns,
            }
        )
    if capture_deadline is not None:
        capture_deadline.checkpoint()
    return captured


def metadata_only(
    repo: Path,
    path: str,
    *,
    sensitive: bool = True,
    capture_deadline: CaptureDeadline | None = None,
) -> dict[str, Any]:
    if capture_deadline is not None:
        capture_deadline.checkpoint()
    normalized = normalize_repo_path(path)
    candidate = repo / normalized
    info = _lstat_repo_entry(repo, normalized)
    if info is None:
        if capture_deadline is not None:
            capture_deadline.checkpoint()
        return _metadata_for_missing(normalized, sensitive=sensitive)
    result: dict[str, Any] = {
        "path": normalized,
        "exists": True,
        "device": info.st_dev,
        "inode": info.st_ino,
        "link_count": info.st_nlink,
        "size": info.st_size,
        "mode": stat.S_IMODE(info.st_mode),
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
        "sensitive": sensitive,
        "content_read": False,
    }
    if stat.S_ISLNK(info.st_mode):
        result["kind"] = "symlink"
        # A symlink target is metadata, but it may itself contain a credential,
        # user name, host, or other sensitive value. Bind it without persisting
        # the raw target in baselines or review bundles.
        target = os.fsencode(os.readlink(candidate))
        after = candidate.lstat()
        if (
            info.st_dev,
            info.st_ino,
            stat.S_IFMT(info.st_mode),
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            stat.S_IFMT(after.st_mode),
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValueError(f"symlink changed during metadata capture: {normalized}")
        result["target_bytes"] = len(target)
        result["target_sha256"] = hashlib.sha256(target).hexdigest()
    elif stat.S_ISDIR(info.st_mode):
        result["kind"] = "directory"
    elif stat.S_ISREG(info.st_mode):
        result["kind"] = "file"
    else:
        result["kind"] = "other"
    if capture_deadline is not None:
        capture_deadline.checkpoint()
    return result


def _regular_file_fingerprint(
    repo: Path,
    path: str,
    *,
    remaining_total: int,
    max_file_bytes: int,
    max_text_patch_file_bytes: int,
    capture_deadline: CaptureDeadline | None = None,
) -> tuple[dict[str, Any], bytes | None, int]:
    if capture_deadline is not None:
        capture_deadline.checkpoint()
    candidate = repo / path
    before = _lstat_repo_entry(repo, path)
    if before is None:
        raise ValueError(f"untracked path disappeared before fingerprint: {path}")
    if before.st_size > max_file_bytes:
        raise ValueError(
            f"untracked file exceeds configured {max_file_bytes}-byte fingerprint budget: {path}"
        )
    if before.st_size > remaining_total:
        raise ValueError("untracked files exceed the aggregate fingerprint byte budget")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(candidate, flags)
    digest = hashlib.sha256()
    retained = bytearray()
    observed = 0
    try:
        opened = os.fstat(descriptor)
        identity = (
            opened.st_dev,
            opened.st_ino,
            stat.S_IFMT(opened.st_mode),
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        expected = (
            before.st_dev,
            before.st_ino,
            stat.S_IFMT(before.st_mode),
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        if identity != expected or not stat.S_ISREG(opened.st_mode):
            raise ValueError(f"untracked file identity changed before fingerprint: {path}")
        while True:
            if capture_deadline is not None:
                capture_deadline.checkpoint()
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            if observed > max_file_bytes or observed > remaining_total:
                raise ValueError(f"untracked file changed beyond fingerprint budget: {path}")
            digest.update(chunk)
            if opened.st_size <= max_text_patch_file_bytes:
                retained.extend(chunk)
        after = os.fstat(descriptor)
        if (
            (
                after.st_dev,
                after.st_ino,
                stat.S_IFMT(after.st_mode),
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            != identity
            or observed != opened.st_size
        ):
            raise ValueError(f"untracked file changed during fingerprint: {path}")
    finally:
        os.close(descriptor)
    content = bytes(retained) if retained else b"" if before.st_size == 0 else None
    is_text = False
    if content is not None and b"\0" not in content:
        try:
            content.decode("utf-8")
            is_text = True
        except UnicodeDecodeError:
            pass
    result = {
        "path": path,
        "kind": "file",
        "exists": True,
        "size": before.st_size,
        "mode": stat.S_IMODE(before.st_mode),
        "sha256": digest.hexdigest(),
        "sensitive": False,
        "content_read": True,
        "text_patch": "included" if is_text else "not-text-or-over-limit",
    }
    if capture_deadline is not None:
        capture_deadline.checkpoint()
    return result, content if is_text else None, observed


def _quoted_git_patch_path(prefix: str, path: str) -> bytes:
    raw = (prefix + path).encode("utf-8", errors="surrogateescape")
    if all(33 <= value <= 126 and value not in {34, 92} for value in raw):
        return raw
    escaped = bytearray(b'"')
    named = {9: b"\\t", 10: b"\\n", 13: b"\\r", 34: b'\\"', 92: b"\\\\"}
    for value in raw:
        if value in named:
            escaped.extend(named[value])
        elif 32 <= value <= 126:
            escaped.append(value)
        else:
            escaped.extend(f"\\{value:03o}".encode("ascii"))
    escaped.extend(b'"')
    return bytes(escaped)


def _new_file_patch(path: str, content: bytes, *, mode: int) -> bytes:
    old_path = _quoted_git_patch_path("a/", path)
    new_path = _quoted_git_patch_path("b/", path)
    git_mode = b"100755" if mode & 0o111 else b"100644"
    file_header = (
        b"diff --git "
        + old_path
        + b" "
        + new_path
        + b"\nnew file mode "
        + git_mode
        + b"\n"
    )
    if not content:
        return file_header
    lines = content.split(b"\n")
    has_final_newline = content.endswith(b"\n")
    if has_final_newline:
        lines.pop()
    header = file_header + b"--- /dev/null\n+++ " + new_path + b"\n"
    body = b"".join(b"+" + line + b"\n" for line in lines)
    if not has_final_newline:
        body += b"\\ No newline at end of file\n"
    return header + f"@@ -0,0 +1,{len(lines)} @@\n".encode("ascii") + body


def filter_untracked_patch(patch: bytes, included_paths: set[str]) -> bytes:
    """Select generated untracked-file patch sections by exact repository path."""

    if not patch or not included_paths:
        return b""
    if not patch.startswith(b"diff --git "):
        raise ValueError("untracked patch has an invalid section header")
    headers = {
        b"diff --git "
        + _quoted_git_patch_path("a/", path)
        + b" "
        + _quoted_git_patch_path("b/", path)
        for path in included_paths
    }
    sections: list[bytes] = []
    for index, part in enumerate(patch.split(b"\ndiff --git ")):
        section = part if index == 0 else b"diff --git " + part
        header = section.split(b"\n", 1)[0]
        if header in headers:
            sections.append(section)
    return b"\n".join(sections)


def repository_snapshot(
    repo: Path,
    *,
    extra_sensitive: list[str] | None = None,
    reviewable_paths: list[str] | None = None,
    allowed_missing_reviewable_paths: set[str] | None = None,
    reference_sensitive_metadata: list[dict[str, Any]] | None = None,
    max_untracked_patch_bytes: int = DEFAULT_MAX_GIT_BYTES,
    max_fingerprint_file_bytes: int = DEFAULT_MAX_FINGERPRINT_FILE_BYTES,
    max_fingerprint_total_bytes: int = DEFAULT_MAX_FINGERPRINT_TOTAL_BYTES,
    max_text_patch_file_bytes: int = DEFAULT_MAX_TEXT_PATCH_FILE_BYTES,
    protect_changed_paths: bool = False,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    max_sensitive_paths: int = DEFAULT_MAX_SENSITIVE_PATHS,
    max_reviewable_paths: int = MAX_REVIEWABLE_PATHS,
    capture_deadline: CaptureDeadline | None = None,
) -> tuple[dict[str, Any], bytes]:
    if capture_deadline is not None:
        capture_deadline.checkpoint()
    normalized_extra = {
        normalize_repo_path(path, label="sensitive path") for path in extra_sensitive or []
    }
    normalized_reviewable = {
        normalize_repo_path(path, label="reviewable path")
        for path in reviewable_paths or []
    }
    canonical_reviewable = canonical_reviewable_paths(
        repo,
        normalized_reviewable,
        allowed_missing=allowed_missing_reviewable_paths,
        max_paths=max_reviewable_paths,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    if canonical_reviewable != sorted(normalized_reviewable):
        raise ValueError(
            "reviewable path no longer matches its sealed repository spelling"
        )
    reviewable_path_metadata(
        repo,
        normalized_reviewable,
        capture_deadline=capture_deadline,
    )
    changes, untracked = repository_changes(
        repo,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    sensitive_paths = discover_sensitive_paths(
        repo,
        normalized_extra,
        reviewable_paths=normalized_reviewable,
        max_sensitive_paths=max_sensitive_paths,
        max_git_seconds=max_git_seconds,
        capture_deadline=capture_deadline,
    )
    reference_by_path: dict[str, dict[str, Any]] | None = None
    reference_paths: set[str] = set()
    if reference_sensitive_metadata is not None:
        reference_by_path = {}
        for item in reference_sensitive_metadata:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("reference sensitive metadata is malformed")
            path = normalize_repo_path(item["path"], label="reference sensitive path")
            if path != item["path"] or path in reference_by_path:
                raise ValueError("reference sensitive metadata paths must be unique and normalized")
            reference_by_path[path] = item
            reference_paths.add(path)
    sensitive_set = set(sensitive_paths) | reference_paths
    if len(sensitive_set) > max_sensitive_paths:
        raise ValueError(
            "sensitive metadata capture exceeds configured "
            f"{max_sensitive_paths}-path budget"
        )
    initial_sensitive_metadata = [
        metadata_only(repo, path, capture_deadline=capture_deadline)
        for path in sorted(sensitive_set)
    ]
    current_sensitive_by_path = {
        item["path"]: item for item in initial_sensitive_metadata
    }
    reference_sensitive_change_observed = (
        reference_by_path is not None
        and current_sensitive_by_path != reference_by_path
    )
    sensitive_change_observed = any(
        is_sensitive_material_path(
            path,
            extra_sensitive=normalized_extra,
            reviewable_paths=normalized_reviewable,
        )
        for item in changes
        for path in (item.get("path", ""), item.get("original_path", ""))
        if path
    )
    quarantine_changed_paths = (
        protect_changed_paths
        or sensitive_change_observed
        or reference_sensitive_change_observed
    )
    for item in changes:
        current = item.get("path", "")
        original = item.get("original_path", "")
        current_sensitive = bool(current) and (
            quarantine_changed_paths
            or is_sensitive_material_path(
                current,
                extra_sensitive=normalized_extra,
                reviewable_paths=normalized_reviewable,
            )
        )
        original_sensitive = bool(original) and (
            quarantine_changed_paths
            or is_sensitive_material_path(
                original,
                extra_sensitive=normalized_extra,
                reviewable_paths=normalized_reviewable,
            )
        )
        if current_sensitive or original_sensitive:
            if current:
                sensitive_set.add(current)
            if original:
                sensitive_set.add(original)
    if len(sensitive_set) > max_sensitive_paths:
        raise ValueError(
            "quarantined metadata capture exceeds configured "
            f"{max_sensitive_paths}-path budget"
        )
    fingerprints: list[dict[str, Any]] = []
    patch_parts: list[bytes] = []
    patch_bytes = 0
    hashed_bytes = 0
    for path in sorted(untracked):
        if capture_deadline is not None:
            capture_deadline.checkpoint()
        sensitive = path in sensitive_set or is_sensitive_material_path(
            path,
            extra_sensitive=normalized_extra,
            reviewable_paths=normalized_reviewable,
        )
        if sensitive:
            sensitive_set.add(path)
        candidate = repo / path
        info = _lstat_repo_entry(repo, path)
        if info is None:
            raise ValueError(f"untracked path disappeared during capture: {path}")
        if sensitive or not stat.S_ISREG(info.st_mode):
            fingerprints.append(
                metadata_only(
                    repo,
                    path,
                    sensitive=sensitive,
                    capture_deadline=capture_deadline,
                )
            )
            continue
        fingerprint, content, observed = _regular_file_fingerprint(
            repo,
            path,
            remaining_total=max_fingerprint_total_bytes - hashed_bytes,
            max_file_bytes=max_fingerprint_file_bytes,
            max_text_patch_file_bytes=max_text_patch_file_bytes,
            capture_deadline=capture_deadline,
        )
        hashed_bytes += observed
        fingerprints.append(fingerprint)
        if content is not None:
            part = _new_file_patch(path, content, mode=fingerprint["mode"])
            if patch_bytes + len(part) > max_untracked_patch_bytes:
                raise ValueError(
                    "untracked text patches exceed the configured aggregate patch budget"
                )
            patch_parts.append(part)
            patch_bytes += len(part)
    sensitive_metadata = [
        metadata_only(repo, path, capture_deadline=capture_deadline)
        for path in sorted(sensitive_set)
    ]
    if capture_deadline is not None:
        capture_deadline.checkpoint()
    return (
        {
            "changes": changes,
            "untracked": fingerprints,
            "sensitive_paths": sensitive_metadata,
            "bounds": {
                "fingerprint_bytes_observed": hashed_bytes,
                "untracked_patch_bytes": patch_bytes,
                "sensitive_change_quarantine": quarantine_changed_paths,
            },
        },
        b"\n".join(patch_parts),
    )


def snapshot_identity(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(
        snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def stable_repository_capture(
    repo: Path,
    *,
    extra_sensitive: list[str] | None = None,
    reviewable_paths: list[str] | None = None,
    allowed_missing_reviewable_paths: set[str] | None = None,
    reference_sensitive_metadata: list[dict[str, Any]] | None = None,
    max_patch_bytes: int = DEFAULT_MAX_GIT_BYTES,
    protect_changed_paths: bool = False,
    max_git_seconds: float = DEFAULT_MAX_GIT_SECONDS,
    max_capture_seconds: float = DEFAULT_MAX_CAPTURE_SECONDS,
    max_sensitive_paths: int = DEFAULT_MAX_SENSITIVE_PATHS,
    max_reviewable_paths: int = MAX_REVIEWABLE_PATHS,
    capture_deadline: CaptureDeadline | None = None,
) -> tuple[dict[str, Any], bytes, bytes, dict[str, str], float, list[dict[str, Any]]]:
    """Require two identical bounded captures before trusting repository state."""

    deadline = capture_deadline or CaptureDeadline(max_capture_seconds)

    def capture_once() -> tuple[
        dict[str, Any],
        bytes,
        bytes,
        dict[str, str],
        list[dict[str, Any]],
    ]:
        deadline.checkpoint()
        git_before = git_identity(
            repo,
            max_git_seconds=max_git_seconds,
            capture_deadline=deadline,
        )
        snapshot, untracked_patch = repository_snapshot(
            repo,
            extra_sensitive=extra_sensitive,
            reviewable_paths=reviewable_paths,
            allowed_missing_reviewable_paths=allowed_missing_reviewable_paths,
            reference_sensitive_metadata=reference_sensitive_metadata,
            max_untracked_patch_bytes=max_patch_bytes,
            protect_changed_paths=protect_changed_paths,
            max_git_seconds=max_git_seconds,
            max_sensitive_paths=max_sensitive_paths,
            max_reviewable_paths=max_reviewable_paths,
            capture_deadline=deadline,
        )
        remaining_patch = max_patch_bytes - len(untracked_patch)
        if remaining_patch <= 0:
            raise ValueError("untracked patch exhausted the aggregate patch budget")
        sensitive = [item["path"] for item in snapshot["sensitive_paths"]]
        patch = tracked_patch(
            repo,
            max_bytes=remaining_patch,
            sensitive_paths=sensitive,
            max_git_seconds=max_git_seconds,
            capture_deadline=deadline,
        )
        canonical_reviewable = canonical_reviewable_paths(
            repo,
            reviewable_paths or [],
            allowed_missing=allowed_missing_reviewable_paths,
            max_paths=max_reviewable_paths,
            max_git_seconds=max_git_seconds,
            capture_deadline=deadline,
        )
        expected_reviewable = sorted(
            {
                normalize_repo_path(path, label="reviewable path")
                for path in reviewable_paths or []
            }
        )
        if canonical_reviewable != expected_reviewable:
            raise ValueError(
                "reviewable path no longer matches its sealed repository spelling"
            )
        reviewable_metadata = reviewable_path_metadata(
            repo,
            expected_reviewable,
            capture_deadline=deadline,
        )
        git_after = git_identity(
            repo,
            max_git_seconds=max_git_seconds,
            capture_deadline=deadline,
        )
        if git_after != git_before:
            raise ValueError("repository Git base changed during capture")
        return snapshot, untracked_patch, patch, git_after, reviewable_metadata

    first = capture_once()
    second = capture_once()
    if first != second:
        raise ValueError("repository state did not stabilize across bounded captures")
    deadline.checkpoint()
    snapshot, untracked_patch, patch, git_after, reviewable_metadata = second
    return (
        snapshot,
        untracked_patch,
        patch,
        git_after,
        deadline.elapsed_seconds(),
        reviewable_metadata,
    )
