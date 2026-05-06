from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.selections.store import list_selections as core_list_selections

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def list_selections(path: OntologyPath):
    """List all named selections in the ontology."""
    with Ontology(path) as ont:
        sels = core_list_selections(ont)

    if not sels:
        return "No selections."

    lines = ["Selections:"]
    for sel in sels:
        lines.append(f"  {sel.locked!r} ({sel.kind}) -> {sel.size} items")
        lines.append(f"    source: {sel.source}")
    return "\n".join(lines)


tool_list_selections = create_tool(
    list_selections,
    name="list_selections",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
