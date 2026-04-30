from mcp.types import ToolAnnotations
from ontoloom.ontology import entities, selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.literals import IRI
from ontoloom.ontology.types import SelectionKind

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
    with Ontology(path) as ont:
        result = entities.find_duplicates(ont, annotation_property, within=within)

        if not result.affected_iris:
            return f"No duplicate {annotation_property} values found."

        source = f"find_duplicates(annotation_property={annotation_property!r})"
        if within:
            source += f", within={within!r}"
        upserted = selections.upsert(
            ont, into, SelectionKind.ENTITIES, result.affected_iris, source=source
        )

    lines = [
        f"Found {result.total_groups} duplicate {annotation_property} values "
        f"across {upserted.cardinality} entities -> {into!r} (sel@{upserted.content_hash})."
    ]
    if upserted.old_cardinality is not None:
        lines.append(f"Overwrote previous ({upserted.old_cardinality} items).")
    lines.append("")

    lines.extend(
        f'  "{group.value}" ({len(group.iris)} entities): {", ".join(group.iris)}'
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
