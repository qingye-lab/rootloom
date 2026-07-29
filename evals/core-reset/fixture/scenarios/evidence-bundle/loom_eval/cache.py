from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


class Cache:
    def __init__(self) -> None:
        self._values: dict[str, object] = {}

    def get(self, key: str, loader: Callable[[], T]) -> T:
        value = self._values.get(key)
        if value:
            return value  # type: ignore[return-value]
        loaded = loader()
        self._values[key] = loaded
        return loaded
