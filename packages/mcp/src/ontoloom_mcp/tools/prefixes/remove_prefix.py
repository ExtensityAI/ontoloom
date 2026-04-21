from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _remove_prefix(path: OntologyPath, name: str):
    """Remove a prefix mapping."""
    with OntologyStore(path) as store:
        store.remove_prefix(name)
        return f"Removed prefix `{name}:`"


tool_remove_prefix = Tool.from_function(
    _remove_prefix,
    name="remove_prefix",
    annotations=ToolAnnotations(destructiveHint=True),
)
