from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.entities.store import find_duplicate_entities
from ontoloom.owl.iri import IRI
from ontoloom.selections.store import get_selection, upsert_selection
from ontoloom.selections.types import SelectionKind
from ontoloom.utils import dquoted

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName

_PREVIEW_GROUPS = 20


def find_duplicates(
    path: OntologyPath,
    into: SelectionName,
    annotation_property: IRI,
    within: SelectionName | None = None,
):
    """Find annotation values shared by multiple entities.

    Reports groups of entities that share the same value for `annotation_property`
    (e.g., "rdfs:label"). Saves all affected entities as an entity selection.

    Args:
    - `into`: Name for the output selection (entities involved in any duplicate).
    - `annotation_property`: The property whose values are checked for duplicates
      (e.g. "rdfs:label").
    - `within`: Optional entity selection to restrict the check to.
    """
    ont = Ontology(path)
    with session(ont) as s:
        if within is not None:
            get_selection(s, within)
        result = find_duplicate_entities(s, annotation_property, within=within)

        if not result.affected_iris:
            return f"No duplicate {annotation_property} values found."

        source = f"find_duplicates(annotation_property={str(annotation_property)!r})"
        if within:
            source += f", within={str(within)!r}"
        upserted = upsert_selection(
            s, into, SelectionKind.ENTITIES, result.affected_iris, source=source
        )
        sel = upserted.selection
        s.commit()

    lines = [
        f"Found {result.total_groups} duplicate {annotation_property} values "
        f"across {sel.size} entities -> {sel.locked!r}."
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
