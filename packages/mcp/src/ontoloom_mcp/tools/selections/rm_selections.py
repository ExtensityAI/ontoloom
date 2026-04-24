from mcp.types import ToolAnnotations
from ontoloom.ontology import selections
from ontoloom.ontology.connection import Ontology

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName


def rm_selections(path: OntologyPath, names: list[SelectionName]):
    """Remove one or more selections by name. Best-effort: removes all that exist, reports any not found."""
    with Ontology(path) as ont:
        dropped, not_found = selections.remove(ont, names)

    parts = []
    if dropped:
        items = ", ".join(f"{name!r} ({count})" for name, count in dropped)
        parts.append(f"Removed {len(dropped)} selections: {items}.")
    if not_found:
        parts.append(f"Not found: {', '.join(repr(n) for n in not_found)}.")
    return " ".join(parts) or "Nothing to remove."


tool_rm_selections = create_tool(
    rm_selections,
    name="rm_selections",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True),
)
