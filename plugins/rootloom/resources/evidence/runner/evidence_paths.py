"""Lexical path checks for outside-repository evidence artifacts."""

from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path
import stat
import sys


def absolute_lexical_path(path: Path) -> Path:
    """Return an absolute path without resolving symlinks."""

    expanded = path.expanduser()
    if any(part == ".." for part in expanded.parts):
        raise ValueError("evidence paths must not contain parent traversal")
    if expanded.is_absolute():
        return expanded
    return Path.cwd() / expanded


def validate_no_symlink_chain(
    path: Path,
    *,
    label: str,
    leaf_may_be_missing: bool,
) -> Path:
    """Reject symlinks in every existing lexical component before resolution."""

    lexical = absolute_lexical_path(path)
    parts = lexical.parts
    if not parts:
        raise ValueError(f"{label} is empty")
    current = Path(parts[0])
    missing_seen = False
    for part in parts[1:]:
        current /= part
        if missing_seen:
            continue
        try:
            info = current.lstat()
        except FileNotFoundError:
            missing_seen = True
            continue
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"{label} must not traverse a symlink: {current}")
        if current != lexical and not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"{label} parent must be a directory: {current}")
    if missing_seen and not leaf_may_be_missing:
        raise ValueError(f"{label} does not exist: {lexical}")
    return lexical


def validate_outside_repository_storage(
    path: Path,
    *,
    repository_roots: Iterable[Path],
    label: str,
) -> Path:
    """Resolve a validated path and reject worktree or Git-storage containment."""

    resolved = path.resolve(strict=False)
    for raw_root in repository_roots:
        root = raw_root.expanduser().resolve(strict=False)
        if resolved == root or resolved.is_relative_to(root):
            raise ValueError(
                f"{label} must be outside the repository worktree and Git common directory"
            )
    return resolved


def fsync_directory(path: Path) -> None:
    """Best-effort directory durability after an atomic evidence transition."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        # Some supported filesystems/platforms do not permit directory fsync.
        pass
    finally:
        os.close(descriptor)


def rename_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically publish a staged directory without replacing any destination."""

    if os.name == "nt":
        # MoveFile semantics used by os.rename on Windows refuse an existing
        # destination, including an empty directory.
        os.rename(source, destination)
        return

    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform == "darwin":
        rename_exclusive = getattr(libc, "renamex_np", None)
        if rename_exclusive is None:
            raise OSError("atomic no-replace directory rename is unavailable")
        rename_exclusive.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename_exclusive.restype = ctypes.c_int
        result = rename_exclusive(source_bytes, destination_bytes, 0x00000004)
    elif sys.platform.startswith("linux"):
        rename_exclusive = getattr(libc, "renameat2", None)
        if rename_exclusive is None:
            raise OSError("atomic no-replace directory rename is unavailable")
        rename_exclusive.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename_exclusive.restype = ctypes.c_int
        result = rename_exclusive(
            -100, source_bytes, -100, destination_bytes, 0x00000001
        )
    else:
        raise OSError(
            f"atomic no-replace directory rename is unsupported on {sys.platform}"
        )
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))
