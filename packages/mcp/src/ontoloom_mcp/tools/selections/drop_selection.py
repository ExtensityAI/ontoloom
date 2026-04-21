from fastmcp.tools import Tool
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _drop_selection(path: OntologyPath, names: list[str]):
    """Drop one or more selections by name. Best-effort: drops all that exist, reports any not found."""
    with OntologyStore(path) as store:
        dropped, not_found = store.drop_selections(names)

    parts = []
    if dropped:
        items = ", ".join(f"{name!r} ({count})" for name, count in dropped)
        parts.append(f"Dropped {len(dropped)} selections: {items}.")
    if not_found:
        parts.append(f"Not found: {', '.join(repr(n) for n in not_found)}.")
    return " ".join(parts) or "Nothing to drop."


tool_drop_selection = Tool.from_function(
    _drop_selection,
    name="drop_selection",
    annotations=None,
)
