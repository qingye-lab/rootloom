"""Small cooperative lock for local Rootloom operations."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import time
from typing import Iterator


class LockFileError(RuntimeError):
    """The lock path could not be used as an ordinary local file."""


class LockBusyError(RuntimeError):
    """Another process already owns the lock path."""

    def __init__(self, path: Path, owner: bytes = b"") -> None:
        detail = owner.decode("utf-8", errors="replace").strip()
        suffix = f" ({detail})" if detail else ""
        super().__init__(f"lock is already held: {path}{suffix}")


def _current_owner(path: Path) -> bytes:
    try:
        return path.read_bytes()[:4096]
    except OSError:
        return b""


def _unlink_lock(path: Path) -> None:
    for attempt in range(20):
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except PermissionError as exc:
            if attempt == 19:
                raise LockFileError(f"could not remove lock {path}: {exc}") from exc
            time.sleep(0.025)


@contextmanager
def simple_lock(path: Path, owner_bytes: bytes | None = None) -> Iterator[int]:
    """Acquire an ordinary create-exclusive lock and remove it on exit."""

    path.parent.mkdir(parents=True, exist_ok=True)
    owner = owner_bytes or f"pid={os.getpid()}\n".encode("ascii")
    if len(owner) > 4096:
        raise LockFileError("lock owner record exceeds 4096 bytes")
    if path.is_symlink():
        raise LockFileError(f"lock path is a symbolic link: {path}")
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise LockBusyError(path, _current_owner(path)) from exc
    except PermissionError as exc:
        if path.exists() or os.name == "nt":
            raise LockBusyError(path, _current_owner(path)) from exc
        raise LockFileError(f"could not create lock {path}: {exc}") from exc
    except OSError as exc:
        raise LockFileError(f"could not create lock {path}: {exc}") from exc
    try:
        os.write(descriptor, owner)
        os.fsync(descriptor)
        yield descriptor
    finally:
        os.close(descriptor)
        _unlink_lock(path)
