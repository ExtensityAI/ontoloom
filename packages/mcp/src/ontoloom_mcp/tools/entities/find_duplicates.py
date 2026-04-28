from mcp.types import ToolAnnotations
from ontoloom.ontology import entities, selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.types import SelectionKind

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName

_PREVIEW_GROUPS = 20


def find_duplicates(
    path: OntologyPath,
    into: SelectionName,
    annotation_property: str,
    within: SelectionName | None = None,
):
    """Find annotation values shared by multiple entities.

    Checks for duplicate values of a specific annotation property (e.g.,
    "rdfs:label") across entities. Saves all affected entities as an entity
    selection for further inspection.

    Use `within` to restrict the check to entities in an existing selection.
    """
    with Ontology(path) as ont:
        result = entities.find_duplicates(ont, annotation_property, within=within)

        if not result.affected_iris:
            return f"No duplicate {annotation_property} values found."

        source = f"find_duplicates(annotation_property={annotation_property!r})"
        if within:
            source += f", within={within!r}"
        content_hash, cardinality, old_cardinality = selections.write(
            ont, into, SelectionKind.ENTITIES, result.affected_iris, source=source
        )

    lines = [
        f"Found {result.total_groups} duplicate {annotation_property} values "
        f"across {cardinality} entities → {into!r} (sel@{content_hash})."
    ]
    if old_cardinality is not None:
        lines.append(f"Overwrote previous ({old_cardinality} items).")
    lines.append("")

    for value, iris in result.groups[:_PREVIEW_GROUPS]:
        lines.append(f'  "{value}" ({len(iris)} entities): {", ".join(iris)}')

    if result.total_groups > _PREVIEW_GROUPS:
        lines.append(f"\n  ... and {result.total_groups - _PREVIEW_GROUPS} more groups.")

    return "\n".join(lines)


tool_find_duplicates = create_tool(
    find_duplicates,
    name="find_duplicates",
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
)
