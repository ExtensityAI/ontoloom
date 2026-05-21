from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.entities.reader import axiom_hashes_for_entity
from ontoloom.entities.reader import get_entity as core_get_entity
from ontoloom.owl.iri import IRI
from ontoloom.selections.persistence import upsert_selection
from ontoloom.selections.types import AxiomSelectionName, SelectionKind
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import build_refs, format_entity_inspect
from ontoloom_mcp.components.locking import format_locked_quoted
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def get_entity(
    path: OntologyPath,
    iri: IRI,
    into: AxiomSelectionName | None = None,
    within: AxiomSelectionName | None = None,
):
    """Get details for a single entity: roles, annotations, and asserted axiom counts by type.

    Does NOT include inherited or inferred information.
    Use `match_axioms` to see the full axiom details.

    - `within`: Scope to a named axiom selection (e.g. `"axioms:my_sel"`).
    - `into`: Save this entity's axiom hashes under the given axiom selection
      (e.g. `"axioms:dog_axioms"`). Entry point for "I want to work on this
      entity's axioms" -> then use `match_axioms(within=...)` or
      `remove_axioms(within=...)` on the result.
    """
    ont = Ontology(path)
    with session(ont) as s:
        info = core_get_entity(s, iri, within=within)
        ref = build_refs(s, [iri])[0]
        result = format_entity_inspect(ref, info)

        if into is not None:
            hashes = axiom_hashes_for_entity(s, iri, within=within)
            source = f"get_entity(iri={dquoted(iri)})"
            upserted = upsert_selection(s, into.bare, SelectionKind.AXIOMS, hashes, source)
            sel = upserted.selection
            sel_msg = f"\n\n{sel.size} axiom hashes -> {format_locked_quoted(sel)}."
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
