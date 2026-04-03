from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from ontoloom.core.ontology.store import OntologyStore

from ontoloom_mcp.components.types import OntologyPath


def _remove_prefix(path: OntologyPath, name: str) -> str:
    """Remove a prefix mapping."""
    with OntologyStore(path) as store:
        try:
            store.remove_prefix(name)
        except ValueError as e:
            raise ToolError(str(e)) from e
        return f"Removed prefix `{name}:`"


tool_remove_prefix = Tool.from_function(_remove_prefix, name="remove_prefix")
