import json
from pathlib import Path
from typing import TypedDict


class User(TypedDict):
    id: int
    display_name: str


def load_users(path: Path) -> list[User]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported schema version")
    return [
        {"id": item["id"], "display_name": item["name"]}
        for item in payload["users"]
    ]


def save_users(path: Path, users: list[User]) -> None:
    payload = {
        "schema_version": 1,
        "users": [
            {"id": item["id"], "name": item["display_name"]}
            for item in users
        ],
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
