from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.selections.store import list_axiom_selections, list_entity_selections

from ontoloom_mcp.components.locking import format_locked_quoted
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def list_selections(path: OntologyPath):
    """List all named selections in the ontology.

    Each row reports total items, missing-count (items that no longer resolve),
    and the source string recorded when the selection was created.
    """
    ont = Ontology(path)
    with session(ont) as s:
        ax_listings = list_axiom_selections(s)
        ent_listings = list_entity_selections(s)
        s.commit()

    if not ax_listings and not ent_listings:
        return "No selections."

    lines = ["Selections:"]
    for listing in ax_listings:
        meta = listing.meta
        missing = listing.missing_count
        missing_note = f", {missing} missing" if missing > 0 else ""
        lines.append(f"  {format_locked_quoted(meta)} (axioms) -> {meta.size} items{missing_note}")
        lines.append(f"    source: {meta.source}")
    for listing in ent_listings:
        meta = listing.meta
        missing = listing.missing_count
        missing_note = f", {missing} missing" if missing > 0 else ""
        lines.append(
            f"  {format_locked_quoted(meta)} (entities) -> {meta.size} items{missing_note}"
        )
        lines.append(f"    source: {meta.source}")
    return "\n".join(lines)


tool_list_selections = create_tool(
    list_selections,
    name="list_selections",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
