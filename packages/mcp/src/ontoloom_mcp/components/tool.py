from collections.abc import Callable
from typing import Any

from fastmcp.tools import Tool
from fastmcp.tools.function_tool import FunctionTool
from mcp.types import ToolAnnotations

from ontoloom_mcp.components.retry import retry_on_busy


def create_tool(
    fn: Callable[..., Any],
    *,
    name: str,
    annotations: ToolAnnotations | None = None,
) -> FunctionTool:
    """Create an MCP tool with retry applied. Error translation happens at the middleware.

    `annotations` convention: omit when all hints take their MCP defaults
    (`readOnlyHint=False`, `destructiveHint=True`, `idempotentHint=False`,
    `openWorldHint=True`). Set hints explicitly only to declare non-default
    behavior -> e.g. read-only tools set `readOnlyHint=True`; idempotent
    mutations set `idempotentHint=True`; benign writes opt out of
    `destructiveHint`.
    """
    return Tool.from_function(retry_on_busy(fn), name=name, annotations=annotations)
