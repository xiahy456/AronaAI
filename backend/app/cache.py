"""Simple exact-match LRU response cache."""

from __future__ import annotations

from collections import OrderedDict


def normalize_query(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


class ResponseCache:
    def __init__(self, max_size: int = 256) -> None:
        self.max_size = max(1, max_size)
        self._data: OrderedDict[str, str] = OrderedDict()

    def get(self, query: str) -> str | None:
        key = normalize_query(query)
        if not key or key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, query: str, response: str) -> None:
        key = normalize_query(query)
        if not key or not response:
            return
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = response
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
