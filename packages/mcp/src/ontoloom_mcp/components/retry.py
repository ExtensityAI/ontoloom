"""SQLite busy-lock retry decorator for MCP tools."""

import functools
import sqlite3
import time
from collections.abc import Callable

from fastmcp.exceptions import ToolError

_MAX_ATTEMPTS = 5
_BASE_DELAY = 0.05
_MAX_DELAY = 1.0


def retry_on_busy[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Retry on sqlite3 'database is locked'. Raises ToolError on exhaustion."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        last: sqlite3.OperationalError | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return fn(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if e.sqlite_errorcode not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                    raise
                last = e
                if attempt < _MAX_ATTEMPTS - 1:
                    delay = min(_MAX_DELAY, _BASE_DELAY * (2**attempt))
                    time.sleep(delay)
        msg = "Database is busy after multiple retries. Another process may be writing. Try again."
        raise ToolError(msg) from last

    return wrapper
