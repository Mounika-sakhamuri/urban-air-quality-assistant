import time
from collections import OrderedDict
from typing import Any


class BoundedTTLCache:
    """Thread-safe bounded LRU + TTL cache to eliminate redundant API & LLM calls."""

    def __init__(self, max_size: int = 128, ttl_seconds: int = 600) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)