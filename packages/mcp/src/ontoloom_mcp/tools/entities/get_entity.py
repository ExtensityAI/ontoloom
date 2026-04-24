from mcp.types import ToolAnnotations
from ontoloom.ontology import entities, selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.literals import IRI
from ontoloom.ontology.types import SelectionKind

from ontoloom_mcp.components.formatting import format_entity_inspect
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName


def get_entity(
    path: OntologyPath,
    iri: IRI,
    within: SelectionName | None = None,
    select: SelectionName | None = None,
):
    """Get details for a single entity: roles, annotations, and asserted axiom counts by type.

    Does NOT include inherited or inferred information.
    Use `search_axioms` to see the full axiom details.

    - `within`: Scope to a named selection. Within an axiom selection: only count axioms
      about this entity that are in the selection. Entity selections have no effect here.
    - `select`: Save this entity's axiom hashes as an axiom selection. Entry point for
      "I want to work on this entity's axioms" — then use `search_axioms(within=...)`
      or `rm_axioms(select=...)` on the result.
    """
    with Ontology(path) as ont:
        info = entities.get(ont, iri, within_selection=within)
        if info is None:
            near = entities.search(ont, query=iri.local_name, limit=3)
            suggestion = ""
            if near.matches:
                names = ", ".join(str(m.iri) for m in near.matches)
                suggestion = f" Similar entities: {names}."
            return f"{iri}\nNot found.{suggestion}\nUse `search_entities` to find entities by name."

        result = format_entity_inspect(iri, info)

        if within:
            sel = selections.get_info(ont, within)
            if sel.kind == SelectionKind.ENTITIES:
                result += (
                    "\n\nNote: `within` with an entity selection has no filtering effect "
                    "on get_entity. To filter displayed axioms, use an axiom selection."
                )

        if select is not None:
            hashes = entities.get_axiom_hashes(ont, iri, within_selection=within)
            source = f"get_entity(iri={str(iri)!r})"
            content_hash, cardinality, old_cardinality = selections.write(
                ont, select, SelectionKind.AXIOMS, hashes, source
            )
            sel_msg = f"\n\n{cardinality} axiom hashes \u2192 {select!r} (sel@{content_hash})."
            if old_cardinality is not None:
                sel_msg += f" Overwrote previous ({old_cardinality} items)."
            result += sel_msg

        return result


tool_get_entity = create_tool(
    get_entity,
    name="get_entity",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
