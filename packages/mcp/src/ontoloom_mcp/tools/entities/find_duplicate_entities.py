from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.entities.reader import find_duplicate_entities as _find_duplicate_entities
from ontoloom.owl.iri import IRI
from ontoloom.selections.store import upsert_entity_selection
from ontoloom.selections.types import EntitySelectionName, WriteMode
from ontoloom.utils import dquoted

from ontoloom_mcp.components.locking import format_locked_quoted
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath

_PREVIEW_GROUPS = 20


def find_duplicate_entities(
    path: OntologyPath,
    into: EntitySelectionName,
    annotation_property: IRI,
    mode: WriteMode = WriteMode.CREATE,
    within: EntitySelectionName | None = None,
):
    """Find annotation values shared by multiple entities.

    Reports groups of entities that share the same value for `annotation_property`
    (e.g., "rdfs:label"). Saves all affected entities as an entity selection.

    Args:
    - `into`: Kind-prefixed name for the output selection
      (e.g. `"entities:dup_labels"`).
    - `annotation_property`: The property whose values are checked for duplicates
      (e.g. "rdfs:label").
    - `mode`: `create` (default) refuses if the selection name already exists; `replace` overwrites it.
    - `within`: Optional entity selection (e.g. `"entities:my_classes"`) to
      restrict the check to.
    """
    ont = Ontology(path)
    with session(ont) as s:
        result = _find_duplicate_entities(s, annotation_property, within=within)

        if not result.affected_iris:
            return f"No duplicate {annotation_property} values found."

        source = f"find_duplicate_entities(annotation_property={dquoted(annotation_property)})"
        if within is not None:
            source += f", within={dquoted(str(within))}"
        upserted = upsert_entity_selection(
            s,
            into.bare,
            result.affected_iris,
            source=source,
            mode=mode,
        )
        sel = upserted.selection
        s.commit()

    lines = [
        f"Found {result.total_groups} duplicate {annotation_property} values "
        f"across {sel.size} entities -> {format_locked_quoted(sel)}."
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


tool_find_duplicate_entities = create_tool(
    find_duplicate_entities,
    name="find_duplicate_entities",
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
)
