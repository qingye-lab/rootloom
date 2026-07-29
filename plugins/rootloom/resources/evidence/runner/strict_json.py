"""Strict JSON decoding for evidence contracts."""

from __future__ import annotations

import json
import math
from typing import Any


class StrictJsonError(ValueError):
    """Evidence JSON is ambiguous or outside the supported JSON grammar."""


def parse_json_object(
    raw: bytes,
    *,
    label: str,
    encoding: str,
) -> dict[str, Any]:
    """Decode one JSON object while rejecting duplicate keys and constants."""

    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not valid {encoding} text") from exc

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise StrictJsonError(f"{label} contains duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise StrictJsonError(f"{label} contains non-standard JSON constant: {value}")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise StrictJsonError(f"{label} contains out-of-range JSON number: {value}")
        return parsed

    try:
        payload = json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
    except StrictJsonError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ValueError(f"{label} is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload
