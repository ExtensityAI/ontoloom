"""SQLite busy-lock retry decorator for MCP tools."""

import functools
import sqlite3
import time

from fastmcp.exceptions import ToolError

_MAX_ATTEMPTS = 5
_BASE_DELAY = 0.05
_MAX_DELAY = 1.0


def retry_on_busy(fn):
    """Retry on sqlite3 'database is locked'. Raises ToolError on exhaustion."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        last: sqlite3.OperationalError | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return fn(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if "locked" not in str(e):
                    raise
                last = e
                if attempt < _MAX_ATTEMPTS - 1:
                    delay = min(_MAX_DELAY, _BASE_DELAY * (2**attempt))
                    time.sleep(delay)
        msg = "Database is busy after multiple retries. Another process may be writing. Try again."
        raise ToolError(msg) from last

    return wrapper
