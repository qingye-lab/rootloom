from __future__ import annotations

import json
from pathlib import Path


SCHEMA_VERSION = 1


def save_plan(path: Path, steps: list[str]) -> None:
    payload = {"schema_version": SCHEMA_VERSION, "steps": list(steps)}
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def load_plan(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported plan schema")
    return list(payload["steps"])
