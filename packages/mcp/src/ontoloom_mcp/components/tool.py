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
    """Create an MCP tool with retry and error translation applied."""
    wrapped = retry_on_busy(translate_errors(fn))
    return Tool.from_function(wrapped, name=name, annotations=annotations)
