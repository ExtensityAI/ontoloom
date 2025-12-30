import re
from abc import ABC, abstractmethod
from pathlib import Path
from threading import RLock

_CK_STR_PATTERN = re.compile(r"^[a-zA-Z0-9_=\-\[\]]+$")

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

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError


class FileCache(Cache):
    """Thread-safe cache that stores values as files in a directory. Keys are mapped to file names."""

    def __init__(self, path: Path, encoding: str = "utf-8"):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        self._path = path
        self._encoding = encoding
        self._lock = RLock()  # allows same thread to acquire multiple times

    def get_path(self, key: CacheKey):
        name = []

        if len(key) == 0 or not isinstance(key[0], str):
            msg = f"Invalid cache key: '{key}'. Either empty or first element not a str!"
            raise KeyError(msg)

        for segment in key:
            if isinstance(segment, (int, bool)):
                name.append(f"[{segment}]")
            else:
                if not _CK_STR_PATTERN.match(segment):
                    msg = f"Invalid cache key segment: '{segment}' of key '{key}'. Did not match pattern: '{_CK_STR_PATTERN.pattern}'"
                    raise KeyError(msg)

                name.extend([".", segment])

        return self._path / "".join(name)

    def exists(self, key: CacheKey):
        with self._lock:
            return self.get_path(key).exists()

    def read(self, key: CacheKey):
        with self._lock:
            return (
                self.get_path(key).read_text(encoding=self._encoding) if self.exists(key) else None
            )

    def write(self, key: CacheKey, value: str):
        with self._lock:
            self.get_path(key).write_text(value, encoding=self._encoding)

    def delete(self, *keys: CacheKey):
        with self._lock:
            for key in keys:
                if not self.exists(key):
                    continue

                self.get_path(key).unlink()

    def clear(self):
        with self._lock:
            for file in self._path.glob("*"):
                if file.is_dir():
                    # ignore dir (not created by this cache?)
                    continue

                file.unlink()
