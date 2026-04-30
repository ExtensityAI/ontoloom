"""Custom middleware for the ontoloom MCP server."""

import logging
import time
from typing import override

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware

logger = logging.getLogger("ontoloom")


class TimingMiddleware(Middleware):
    """Log wall-clock time per tool call."""

    @override
    async def on_call_tool(self, context, call_next):
        start = time.perf_counter()
        try:
            return await call_next(context)
        finally:
            elapsed = time.perf_counter() - start
            logger.info("tool %s completed in %.3fs", context.message.name, elapsed)


class LastResortMiddleware(Middleware):
    """Catch unhandled exceptions so clients get a clean error instead of a crash."""

    @override
    async def on_call_tool(self, context, call_next):
        try:
            return await call_next(context)
        except ToolError:
            raise
        except Exception as e:
            logger.exception("Unhandled exception in tool %s", context.message.name)
            msg = f"Internal error: {type(e).__name__}: {e}"
            raise ToolError(msg) from e
