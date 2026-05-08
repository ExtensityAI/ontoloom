from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.entities.store import axiom_hashes_for_entity
from ontoloom.entities.store import get_entity as core_get_entity
from ontoloom.owl.iri import IRI
from ontoloom.selections.store import get_selection, upsert_selection
from ontoloom.selections.types import SelectionKind
from ontoloom.transactions import session

from ontoloom_mcp.components.formatting import format_entity_inspect
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName


def get_entity(
    path: OntologyPath,
    iri: IRI,
    into: SelectionName | None = None,
    within: SelectionName | None = None,
):
    """Get details for a single entity: roles, annotations, and asserted axiom counts by type.

    Does NOT include inherited or inferred information.
    Use `match_axioms` to see the full axiom details.

    - `within`: Scope to a named selection. Within an axiom selection: only count axioms
      about this entity that are in the selection. Entity selections have no effect here.
    - `into`: Save this entity's axiom hashes as an axiom selection. Entry point for
      "I want to work on this entity's axioms" -> then use `match_axioms(within=...)`
      or `remove_axioms(within=...)` on the result.
    """
    ont = Ontology(path)
    with session(ont) as s:
        info = core_get_entity(s, iri, within=within)
        result = format_entity_inspect(iri, info)

        if within:
            sel = get_selection(s, within)
            if sel.kind == SelectionKind.ENTITIES:
                result += (
                    "\n\nNote: `within` with an entity selection has no filtering effect "
                    "on get_entity. To filter displayed axioms, use an axiom selection."
                )

        if into is not None:
            hashes = axiom_hashes_for_entity(s, iri, within=within)
            source = f"get_entity(iri={str(iri)!r})"
            upserted = upsert_selection(s, into, SelectionKind.AXIOMS, hashes, source)
            sel = upserted.selection
            sel_msg = f"\n\n{sel.size} axiom hashes -> {sel.locked!r}."
            if upserted.previous_size is not None:
                sel_msg += f" Overwrote previous ({upserted.previous_size} items)."
            result += sel_msg

        s.commit()

    return result


tool_get_entity = create_tool(
    get_entity,
    name="get_entity",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
