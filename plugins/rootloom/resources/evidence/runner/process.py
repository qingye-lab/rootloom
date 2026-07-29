"""Streaming, bounded subprocess execution without a shell."""

from __future__ import annotations

import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time
from typing import BinaryIO

from .contracts import VerificationResult


READ_CHUNK_BYTES = 64 * 1024
TERMINATE_GRACE_SECONDS = 0.5
KILL_GRACE_SECONDS = 1.5
POST_EXIT_PIPE_GRACE_SECONDS = 0.2
POST_EXIT_TREE_GRACE_SECONDS = 0.5


class _WindowsJob:
    def __init__(self) -> None:
        self.handle = None
        self.supported = False
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class BASIC_LIMIT(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED_LIMIT(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class ACCOUNTING(ctypes.Structure):
            _fields_ = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._accounting = ACCOUNTING
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self._kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self._kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self._kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
        ]
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = self._kernel32.CreateJobObjectW(None, None)
        if not handle:
            return
        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        if not self._kernel32.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            self._kernel32.CloseHandle(handle)
            return
        self.handle = handle

    def assign(self, process: subprocess.Popen[bytes]) -> bool:
        if self.handle is None:
            return False
        process_handle = self._wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
        self.supported = bool(
            self._kernel32.AssignProcessToJobObject(self.handle, process_handle)
        )
        return self.supported

    def active(self) -> bool | None:
        if not self.supported or self.handle is None:
            return None
        info = self._accounting()
        if not self._kernel32.QueryInformationJobObject(
            self.handle,
            1,
            self._ctypes.byref(info),
            self._ctypes.sizeof(info),
            None,
        ):
            return None
        return info.ActiveProcesses > 0

    def terminate(self) -> bool:
        if not self.supported or self.handle is None:
            return False
        return bool(self._kernel32.TerminateJobObject(self.handle, 125))

    def close(self) -> None:
        if self.handle is not None:
            self._kernel32.CloseHandle(self.handle)
            self.handle = None


def _read_pipe(pipe: BinaryIO, output: queue.Queue[bytes | None]) -> None:
    try:
        while True:
            chunk = pipe.read(READ_CHUNK_BYTES)
            if not chunk:
                break
            output.put(chunk)
    except (OSError, ValueError):
        pass
    finally:
        try:
            output.put(None, timeout=0.1)
        except queue.Full:
            pass


def _posix_group_active(process: subprocess.Popen[bytes]) -> bool:
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _controlled_tree_active(
    process: subprocess.Popen[bytes], windows_job: _WindowsJob | None
) -> bool | None:
    if os.name != "nt":
        return _posix_group_active(process)
    if windows_job is not None and windows_job.supported:
        return windows_job.active()
    # Without Job Object support, taskkill remains the termination fallback.
    # Parent liveness is still knowable; detached descendants remain covered by
    # the documented process-group-only limitation.
    return process.poll() is None


def _wait_inactive(active, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = active()
        if state is False:
            return True
        if state is None:
            return False
        time.sleep(0.025)
    return active() is False


def _controlled_tree_inactive_after_grace(
    process: subprocess.Popen[bytes],
    windows_job: _WindowsJob | None,
    timeout: float,
) -> bool:
    """Allow exited processes to drain from OS process-tree accounting."""

    def active() -> bool | None:
        return _controlled_tree_active(process, windows_job)

    state = active()
    if state is False:
        return True
    if state is None:
        return False
    return _wait_inactive(active, timeout)


def _terminate_tree(
    process: subprocess.Popen[bytes], windows_job: _WindowsJob | None
) -> bool:
    if os.name == "nt":
        if windows_job is not None and windows_job.supported and windows_job.terminate():
            return _wait_inactive(windows_job.active, KILL_GRACE_SECONDS)
        else:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=KILL_GRACE_SECONDS,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                return False
        return _wait_inactive(lambda: process.poll() is None, KILL_GRACE_SECONDS)
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    if _wait_inactive(lambda: _posix_group_active(process), TERMINATE_GRACE_SECONDS):
        return True
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return _wait_inactive(lambda: _posix_group_active(process), KILL_GRACE_SECONDS)


def _retain_tail(tail: bytearray, chunk: bytes, limit: int) -> None:
    tail.extend(chunk)
    if len(tail) > limit:
        del tail[: len(tail) - limit]


def run_command(
    argv: list[str],
    *,
    cwd: Path,
    timeout: float,
    max_output_bytes: int,
    inherit_stdin: bool = True,
) -> tuple[VerificationResult, bytes]:
    started = time.monotonic()
    output_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=4)
    windows_job = _WindowsJob() if os.name == "nt" else None
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=None if inherit_stdin else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
            creationflags=creationflags,
        )
    except OSError as exc:
        message = f"Rootloom: command could not run: {exc}\n".encode(
            "utf-8", errors="replace"
        )[:max_output_bytes]
        return (
            VerificationResult(
                command=argv,
                exit_code=126,
                duration_seconds=round(time.monotonic() - started, 3),
                passed=False,
                output_bytes_observed=len(message),
                output_bytes_retained=len(message),
            ),
            message,
        )
    if windows_job is not None:
        windows_job.assign(process)
    assert process.stdout is not None
    reader = threading.Thread(
        target=_read_pipe, args=(process.stdout, output_queue), daemon=True
    )
    reader.start()
    deadline = started + timeout
    tail = bytearray()
    observed = 0
    eof = False
    timed_out = False
    output_limit_exceeded = False
    leaked_descendant = False
    converged = True
    exit_code: int | None = None
    parent_exit_observed: float | None = None
    try:
        while not eof:
            now = time.monotonic()
            if now >= deadline and not timed_out:
                timed_out = True
                converged = _terminate_tree(process, windows_job)
            try:
                item = output_queue.get(timeout=0.05)
            except queue.Empty:
                polled = process.poll()
                if polled is not None:
                    exit_code = polled
                    parent_exit_observed = parent_exit_observed or now
                    if now - parent_exit_observed >= POST_EXIT_PIPE_GRACE_SECONDS:
                        if not _controlled_tree_inactive_after_grace(
                            process,
                            windows_job,
                            POST_EXIT_TREE_GRACE_SECONDS,
                        ):
                            leaked_descendant = True
                            converged = _terminate_tree(process, windows_job)
                            try:
                                process.stdout.close()
                            except OSError:
                                pass
                            eof = True
                if timed_out and process.poll() is not None:
                    eof = True
                continue
            if item is None:
                eof = True
                continue
            observed += len(item)
            _retain_tail(tail, item, max_output_bytes)
            if observed > max_output_bytes and not output_limit_exceeded:
                output_limit_exceeded = True
                converged = _terminate_tree(process, windows_job)
        try:
            exit_code = process.wait(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            converged = _terminate_tree(process, windows_job)
            try:
                exit_code = process.wait(timeout=KILL_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                converged = False
                exit_code = 125
        if not _controlled_tree_inactive_after_grace(
            process,
            windows_job,
            POST_EXIT_TREE_GRACE_SECONDS,
        ):
            leaked_descendant = True
            converged = _terminate_tree(process, windows_job) and converged
    finally:
        try:
            process.stdout.close()
        except (OSError, ValueError):
            pass
        if windows_job is not None:
            windows_job.close()
    if timed_out:
        exit_code = 124
        _retain_tail(tail, b"\nRootloom: command timed out\n", max_output_bytes)
    elif output_limit_exceeded:
        exit_code = 125
        _retain_tail(
            tail,
            b"\nRootloom: output limit exceeded; process tree terminated\n",
            max_output_bytes,
        )
    elif leaked_descendant:
        exit_code = 125
        _retain_tail(
            tail,
            b"\nRootloom: command left descendant processes; process tree terminated\n",
            max_output_bytes,
        )
    if not converged:
        exit_code = 125
        _retain_tail(
            tail,
            b"\nRootloom: process-tree convergence could not be proven\n",
            max_output_bytes,
        )
    retained = bytes(tail)
    result = VerificationResult(
        command=argv,
        exit_code=int(exit_code if exit_code is not None else 125),
        duration_seconds=round(time.monotonic() - started, 3),
        passed=exit_code == 0 and converged and not leaked_descendant,
        timed_out=timed_out,
        output_bytes_observed=observed,
        output_bytes_retained=len(retained),
        output_limit_exceeded=output_limit_exceeded,
        process_tree_converged=converged,
    )
    return result, retained
