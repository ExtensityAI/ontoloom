from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.entities.reader import axiom_hashes_for_entity
from ontoloom.entities.reader import get_entity as core_get_entity
from ontoloom.entities.types import EntityInfo
from ontoloom.owl.iri import IRI
from ontoloom.selections.store import upsert_axiom_selection
from ontoloom.selections.types import AxiomSelectionName
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import Ref, build_refs, format_ref, format_roles
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
        result = _format_entity_inspect(ref, info)

        if into is not None:
            hashes = axiom_hashes_for_entity(s, iri, within=within)
            source = f"get_entity(iri={dquoted(iri)})"
            upserted = upsert_axiom_selection(s, into.bare, hashes, source)
            sel = upserted.selection
            sel_msg = f"\n\n{sel.size} axiom hashes -> {format_locked_quoted(sel)}."
            if upserted.previous_size is not None:
                sel_msg += f" Overwrote previous ({upserted.previous_size} items)."
            result += sel_msg

        s.commit()

    return result


def _format_entity_inspect(ref: Ref, info: EntityInfo):
    lines = [f"{format_ref(ref)} ({format_roles(info.roles)})", ""]

    if info.annotations:
        lines.append("Annotations:")
        lines.extend(f"  {ann.property} {dquoted(ann.value)}" for ann in info.annotations)
        lines.append("")

    total = sum(info.axiom_counts.values())
    if total:
        lines.append(f"Axioms (asserted): {total}")
        for typ, count in info.axiom_counts.most_common():
            lines.append(f"  {count} {typ}")

    return "\n".join(lines).rstrip()


tool_get_entity = create_tool(
    get_entity,
    name="get_entity",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
