"""Shared error-handling decorator for MCP tools."""

import functools
import sqlite3

from fastmcp.exceptions import ToolError


def handle_tool_errors(fn):
    """Translate store/OS exceptions into user-facing ToolError messages."""

    # TODO: this does not seem like a best practice, do not like it

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except FileNotFoundError:
            msg = "Ontology not found at the given path. Use create_ontology first."
            raise ToolError(msg) from None
        except FileExistsError as e:
            raise ToolError(str(e)) from None
        except ValueError as e:
            raise ToolError(str(e)) from None
        except sqlite3.OperationalError as e:
            msg = str(e)
            if "locked" in msg:
                msg = "Database is busy — another process may be writing to it. Try again."
            else:
                msg = f"Database error: {msg}"
            raise ToolError(msg) from None
        except sqlite3.DatabaseError as e:
            msg = f"Database error: {e}"
            raise ToolError(msg) from None
        except OSError as e:
            msg = f"File error: {e}"
            raise ToolError(msg) from None

    return wrapper
