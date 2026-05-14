from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.entities.store import find_duplicate_entities
from ontoloom.owl.iri import IRI
from ontoloom.query._selection_ref import resolve_selection
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import SelectionKind, SelectionName
from ontoloom.utils import dquoted

from ontoloom_mcp.components.selection_refs import SelectionRefParam
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath

_PREVIEW_GROUPS = 20


def find_duplicates(
    path: OntologyPath,
    into: SelectionRefParam,
    annotation_property: IRI,
    within: SelectionRefParam | None = None,
):
    """Find annotation values shared by multiple entities.

    Reports groups of entities that share the same value for `annotation_property`
    (e.g., "rdfs:label"). Saves all affected entities as an entity selection.

    Args:
    - `into`: Kind-prefixed name for the output selection
      (e.g. `"entities:dup_labels"`).
    - `annotation_property`: The property whose values are checked for duplicates
      (e.g. "rdfs:label").
    - `within`: Optional entity selection (e.g. `"entities:my_classes"`) to
      restrict the check to.
    """
    if into.kind != SelectionKind.ENTITIES:
        msg = (
            f"find_duplicates produces an ENTITIES selection; "
            f"got 'into={into}' with kind={into.kind}"
        )
        raise ValueError(msg)

    ont = Ontology(path)
    with session(ont) as s:
        resolved_within = resolve_selection(s, within) if within is not None else None
        result = find_duplicate_entities(s, annotation_property, within=resolved_within)

        if not result.affected_iris:
            return f"No duplicate {annotation_property} values found."

        source = f"find_duplicates(annotation_property={dquoted(annotation_property)})"
        if within is not None:
            source += f", within={dquoted(str(within))}"
        upserted = upsert_selection(
            s,
            SelectionName(into.bare_name),
            SelectionKind.ENTITIES,
            result.affected_iris,
            source=source,
        )
        sel = upserted.selection
        s.commit()

    lines = [
        f"Found {result.total_groups} duplicate {annotation_property} values "
        f"across {sel.size} entities -> {dquoted(sel.locked)}."
    ]
    if upserted.previous_size is not None:
        lines.append(f"Overwrote previous ({upserted.previous_size} items).")
    lines.append("")

    lines.extend(
        f"  {dquoted(group.value)} ({len(group.iris)} entities): {', '.join(group.iris)}"
        for group in result.groups[:_PREVIEW_GROUPS]
    )

    if result.total_groups > _PREVIEW_GROUPS:
        lines.append(f"\n  ... and {result.total_groups - _PREVIEW_GROUPS} more groups.")

    return "\n".join(lines)


tool_find_duplicates = create_tool(
    find_duplicates,
    name="find_duplicates",
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
)
