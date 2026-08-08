#!/usr/bin/env python3
"""Verify the reviewed VibeLoft browser runtime build without emitting events."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys


SCRIPT_URL = "https://vibeloft.ai/telemetry/v1.js"
MAX_RUNTIME_BYTES = 1_000_000
EXPECTED_RUNTIME_SHA256 = "0901374715934a0234cda527cd95fd4d3c66c989fddd672d06c9df3f43d05bf5"
REQUIRED_BUILD_DECLARATIONS = (
    "VibeLoft-Telemetry",
    "VibeLoft AWS API",
)


def runtime_errors(
    source: bytes,
    *,
    expected_digest: str = EXPECTED_RUNTIME_SHA256,
) -> tuple[list[str], str]:
    digest = hashlib.sha256(source).hexdigest()
    errors: list[str] = []
    if len(source) > MAX_RUNTIME_BYTES:
        errors.append("official runtime exceeds the bounded verification size")
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError:
        errors.append("official runtime is not valid UTF-8")
        text = ""
    errors.extend(
        f"missing official build declaration: {declaration}"
        for declaration in REQUIRED_BUILD_DECLARATIONS
        if declaration not in text
    )
    if digest != expected_digest:
        errors.append(
            "reviewed official runtime build changed: "
            f"expected sha256={expected_digest}, observed sha256={digest}; "
            "repeat the governed zero-egress browser review before updating the digest"
        )
    return errors, digest


def main() -> int:
    curl = shutil.which("curl")
    if curl is None:
        print("ERROR: curl is required for the TLS-verified runtime check", file=sys.stderr)
        return 1
    try:
        completed = subprocess.run(
            [
                curl,
                "--fail",
                "--silent",
                "--show-error",
                "--location",
                "--proto",
                "=https",
                "--tlsv1.2",
                "--max-time",
                "15",
                "--max-filesize",
                str(MAX_RUNTIME_BYTES),
                SCRIPT_URL,
            ],
            check=False,
            capture_output=True,
            timeout=20,
        )
        if completed.returncode != 0:
            raise OSError(completed.stderr.decode("utf-8", errors="replace").strip())
        source = completed.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: unable to read official VibeLoft runtime: {exc}", file=sys.stderr)
        return 1

    errors, digest = runtime_errors(source)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Reviewed official VibeLoft runtime build passed (sha256={digest}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
