from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.entities.reader import find_duplicate_entities as _find_duplicate_entities
from ontoloom.entities.types import DuplicateGroup
from ontoloom.owl.iri import IRI
from ontoloom.selections.store import upsert_entity_selection
from ontoloom.selections.types import SelectionKind, SelectionName, WriteMode
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import (
    PREVIEW_ROWS,
    FindDuplicatesSource,
    format_kinded_count,
    format_saved_line,
    format_selection_write,
    format_source,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def find_duplicate_entities(
    path: OntologyPath,
    into: SelectionName,
    annotation_property: IRI,
    mode: WriteMode = WriteMode.CREATE,
    within: SelectionName | None = None,
):
    """Find annotation values shared by multiple entities.

    Reports groups of entities that share the same value for `annotation_property`
    (e.g., "rdfs:label"). Saves all affected entities as an entity selection;
    when no duplicates exist, an empty selection is still written.

    Args:
    - `into`: Name for the output selection (e.g. `"dup_labels"`).
    - `annotation_property`: The property whose values are checked for duplicates
      (e.g. "rdfs:label").
    - `mode`: `create` (default) refuses if the selection name already exists; `replace` overwrites it.
    - `within`: Optional entity selection (e.g. `"my_classes"`) to
      restrict the check to.
    """
    src = FindDuplicatesSource(annotation_property=annotation_property, within=within)

    ont = Ontology(path)
    with session(ont) as s:
        result = _find_duplicate_entities(s, annotation_property, within=within)
        upserted = upsert_entity_selection(
            s, into, result.affected_iris, format_source(src), mode=mode
        )
        s.commit()

    if not result.groups:
        return format_selection_write(upserted, None, src)

    prop = str(annotation_property)
    g = result.total_groups
    head = f"{format_saved_line(upserted)} {g} duplicate {prop} values:"
    body = _format_groups(result.groups)
    return f"{head}\n\n{body}"


def _format_groups(groups: tuple[DuplicateGroup, ...]):
    lines = [_format_group_line(group) for group in groups[:PREVIEW_ROWS]]

    if len(groups) > PREVIEW_ROWS:
        lines.append(f"\n  ... and {len(groups) - PREVIEW_ROWS} more.")
    return "\n".join(lines)


def _format_group_line(group: DuplicateGroup):
    count = format_kinded_count(SelectionKind.ENTITIES, len(group.iris))
    iris = ", ".join(group.iris)
    return f"  {dquoted(group.value)} ({count}): {iris}"


tool_find_duplicate_entities = create_tool(
    find_duplicate_entities,
    name="find_duplicate_entities",
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
)
