"""Custom middleware for the ontoloom MCP server."""

import logging
import time
from typing import override

import mcp.types as mt
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

from ontoloom_mcp.components.errors import TRANSLATABLE, format_error

logger = logging.getLogger("ontoloom")


class TimingMiddleware(Middleware):
    """Log wall-clock time per tool call."""

    @override
    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        start = time.perf_counter()
        try:
            return await call_next(context)
        finally:
            elapsed = time.perf_counter() - start
            logger.info("tool %s completed in %.3fs", context.message.name, elapsed)


class LastResortMiddleware(Middleware):
    """Catch unhandled exceptions so clients get a clean error instead of a crash.

    Routes translatable exceptions (OntoloomError, FileNotFoundError,
    PermissionError) through the project's hint formatters so errors raised
    during input validation, before the per-tool decorator runs, still get a
    focused message. Other exceptions are logged and surfaced with a generic
    prefix.
    """

    @override
    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        try:
            return await call_next(context)
        except ToolError:
            raise
        except TRANSLATABLE as e:
            raise ToolError(format_error(e)) from None
        except Exception as e:
            logger.exception("Unhandled exception in tool %s", context.message.name)
            msg = f"Internal error: {type(e).__name__}: {e}"
            raise ToolError(msg) from e
