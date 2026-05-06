from collections.abc import Callable
from typing import Any

from fastmcp.tools import Tool
from fastmcp.tools.function_tool import FunctionTool
from mcp.types import ToolAnnotations

from ontoloom_mcp.components.errors import translate_errors
from ontoloom_mcp.components.retry import retry_on_busy


def create_tool(
    fn: Callable[..., Any],
    *,
    name: str,
    annotations: ToolAnnotations | None = None,
) -> FunctionTool:
    """Create an MCP tool with retry and error translation applied.

    `annotations` convention: omit when all hints take their MCP defaults
    (`readOnlyHint=False`, `destructiveHint=True`, `idempotentHint=False`,
    `openWorldHint=True`). Set hints explicitly only to declare non-default
    behavior -> e.g. read-only tools set `readOnlyHint=True`; idempotent
    mutations set `idempotentHint=True`; benign writes opt out of
    `destructiveHint`.
    """
    wrapped = retry_on_busy(translate_errors(fn))
    return Tool.from_function(wrapped, name=name, annotations=annotations)
