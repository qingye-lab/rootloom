"""Verification command parsing and execution."""

from __future__ import annotations

import os
from pathlib import Path
import shlex

from .contracts import VerificationResult
from .process import run_command


def split_command(raw: str, *, windows: bool | None = None) -> list[str]:
    if windows is None:
        windows = os.name == "nt"
    argv = shlex.split(raw, posix=not windows)
    if windows:
        argv = [
            token[1:-1]
            if len(token) >= 2 and token[0] == token[-1] and token[0] in {'"', "'"}
            else token
            for token in argv
        ]
    if not argv:
        raise ValueError("verification command cannot be empty")
    return argv


def verify(
    commands: list[str],
    *,
    repo: Path,
    timeout: int,
    max_output_bytes: int,
) -> tuple[list[VerificationResult], bytes]:
    parsed_commands = [(raw, split_command(raw)) for raw in commands]
    results: list[VerificationResult] = []
    chunks: list[bytes] = []
    remaining_output = max_output_bytes
    for raw, argv in parsed_commands:
        header = (f"$ {raw}\n").encode("utf-8")
        separator_size = 1 if chunks else 0
        available = remaining_output - separator_size
        if available <= len(header) + 1:
            results.append(
                VerificationResult(
                    command=argv,
                    exit_code=125,
                    duration_seconds=0.0,
                    passed=False,
                )
            )
            notice = b"Rootloom: aggregate verification output budget exhausted\n"
            if available > 0:
                chunks.append(notice[:available])
            break
        result, output = run_command(
            argv,
            cwd=repo,
            timeout=timeout,
            max_output_bytes=available - len(header) - 1,
        )
        results.append(result)
        chunk = header + output.rstrip() + b"\n"
        chunks.append(chunk)
        remaining_output -= separator_size + len(chunk)
        if not result.passed:
            break
    return results, b"\n".join(chunks)
