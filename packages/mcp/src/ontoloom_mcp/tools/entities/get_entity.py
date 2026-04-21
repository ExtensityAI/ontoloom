from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.models.literals import IRI
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.formatting import format_entity_inspect
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _get_entity(path: OntologyPath, iri: IRI, within: str = "", select: str = ""):
    """Get details for a single entity: roles, annotations, and asserted axiom counts by type.

    Does NOT include inherited or inferred information.
    Use `search_axioms` to see the full axiom details.

    - `within`: If kind='axioms', only count axioms about this entity that are in the
      selection. If kind='entities', no filtering effect.
    - `select`: Save this entity's axiom hashes as an axiom selection. Convenient entry
      point for "I'm going to work on this entity's axioms."
    """
    if select and "@" in select:
        msg = "Selection names must not contain '@'."
        raise ValueError(msg)

    within_name = within or None

    with OntologyStore(path) as store:
        info = store.get_entity(iri, within=within_name)
        if info is None:
            near = store.search_entities(query=iri.local_name, limit=3)
            suggestion = ""
            if near.matches:
                names = ", ".join(str(m.iri) for m in near.matches)
                suggestion = f" Similar entities: {names}."
            return f"{iri}\nNot found.{suggestion}\nUse `search_entities` to find entities by name."

        result = format_entity_inspect(iri, info)

        if within_name:
            sel = store._get_selection(within_name)
            if sel["kind"] == "entities":
                result += (
                    "\n\nNote: `within` with an entity selection has no filtering effect "
                    "on get_entity. To filter displayed axioms, use an axiom selection."
                )

        if select:
            hashes = store.get_entity_axiom_hashes(iri, within=within_name)
            source = f"get_entity(iri={str(iri)!r})"
            content_hash, cardinality, old_cardinality = store._write_selection(
                select, "axioms", hashes, source
            )
            sel_msg = f"\n\n{cardinality} axiom hashes \u2192 {select!r} (sel@{content_hash})."
            if old_cardinality is not None:
                sel_msg += f" Overwrote previous ({old_cardinality} items)."
            result += sel_msg

        return result


tool_get_entity = Tool.from_function(
    _get_entity,
    name="get_entity",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
