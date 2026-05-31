from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.selections.store import list_axiom_selections, list_entity_selections
from ontoloom.selections.types import AxiomSelectionListing, EntitySelectionListing

from ontoloom_mcp.components.formatting import format_list_row
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def list_selections(path: OntologyPath):
    """List all named selections in the ontology.

    Each row reports total items, missing-count (items that no longer resolve),
    and the source string recorded when the selection was created. Axiom
    selections render before entity selections; within each kind, listings are
    returned in creation order (then name).
    """
    ont = Ontology(path)
    with session(ont) as s:
        listings: list[AxiomSelectionListing | EntitySelectionListing] = [
            *list_axiom_selections(s),
            *list_entity_selections(s),
        ]
        s.commit()

    if not listings:
        return "No selections."

    rows = [
        format_list_row(
            listing.meta,
            listing.present_count,
            listing.missing_count,
            listing.meta.source,
        )
        for listing in listings
    ]
    return "\n".join(["Selections:", *rows])


tool_list_selections = create_tool(
    list_selections,
    name="list_selections",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
