from abc import ABC, abstractmethod
from pathlib import Path
from threading import RLock

CacheKey = tuple[str | int | bool, ...]


class Cache(ABC):
    @abstractmethod
    def exists(self, key: CacheKey) -> bool:
        raise NotImplementedError

    @abstractmethod
    def read(self, key: CacheKey) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def write(self, key: CacheKey, value: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, *keys: CacheKey) -> None:
        raise NotImplementedError


class DirectoryCache(Cache):
    """Thread-safe cache that stores values in a directory structure. Keys are mapped to paths."""

    def __init__(self, path: Path, encoding: str = "utf-8"):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        self._path = path
        self._encoding = encoding
        self._lock = RLock()  # allows same thread to acquire multiple times

    @property
    def path(self):
        return self._path

    def _get_path(self, key: CacheKey):
        return Path(self._path, *map(str, key))

    def exists(self, key: CacheKey):
        with self._lock:
            return self._get_path(key).exists()

    def read(self, key: CacheKey):
        with self._lock:
            return (
                self._get_path(key).read_text(encoding=self._encoding) if self.exists(key) else None
            )

    def write(self, key: CacheKey, value: str):
        with self._lock:
            p = self._get_path(key)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(value, encoding=self._encoding)

    def delete(self, *keys: CacheKey):
        with self._lock:
            for key in keys:
                if not self.exists(key):
                    continue

                self._get_path(key).unlink()
