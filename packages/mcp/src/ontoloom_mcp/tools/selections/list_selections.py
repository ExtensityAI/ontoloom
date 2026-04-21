from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _list_selections(path: OntologyPath):
    """List all named selections in the ontology."""
    with OntologyStore(path) as store:
        selections = store.list_selections()

    if not selections:
        return "No selections."

    lines = ["Selections:"]
    for sel in selections:
        lines.append(
            f"  {sel['name']} ({sel['kind']}, sel@{sel['hash']}) \u2014 {sel['cardinality']} items"
        )
        lines.append(f"    source: {sel['source']}")
        lines.append(f"    created: {sel['created_at']}")
    return "\n".join(lines)


tool_list_selections = Tool.from_function(
    _list_selections,
    name="list_selections",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
