from typing import TypedDict


class User(TypedDict):
    id: int
    name: str


def render_user(user: User) -> str:
    return user["name"]
