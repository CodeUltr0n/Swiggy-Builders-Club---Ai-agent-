"""Persistent memory layer placeholder."""

class MemoryStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or "memory.db"
        self._store = {}

    def get(self, key: str, default=None):
        return self._store.get(key, default)

    def set(self, key: str, value) -> None:
        self._store[key] = value

    def all(self):
        return dict(self._store)
