import shutil
from abc import ABC, abstractmethod
from collections.abc import Callable
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
    def write(self, key: CacheKey, value: str):
        raise NotImplementedError

    @abstractmethod
    def delete(self, *keys: CacheKey):
        raise NotImplementedError

    @abstractmethod
    def clear(self):
        raise NotImplementedError


class DirectoryCache(Cache):
    """Thread-safe cache that stores values in a directory structure. Keys segments are mapped to directory names; the last one denotes the file name."""

    def __init__(self, path: Path, encoding: str = "utf-8"):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        self._path = path
        self._encoding = encoding
        self._lock = RLock()  # allows same thread to acquire multiple times

    def _get_cache_file_path(self, key: CacheKey):
        return self._path / Path(*map(str, key))

    def exists(self, key: CacheKey) -> bool:
        with self._lock:
            return self._get_cache_file_path(key).exists()

    def read(self, key: CacheKey) -> str | None:
        with self._lock:
            return (
                self._get_cache_file_path(key).read_text(encoding=self._encoding)
                if self.exists(key)
                else None
            )

    def write(self, key: CacheKey, value: str):
        with self._lock:
            path = self._get_cache_file_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding=self._encoding)

    def delete(self, *keys: CacheKey):
        with self._lock:
            for key in keys:
                path = self._get_cache_file_path(key)

                if self.exists(key):
                    path.unlink()

    def clear(self):
        with self._lock:
            shutil.rmtree(self._path)
            self._path.mkdir(parents=True, exist_ok=True)
