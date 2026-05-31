from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.entities.reader import search_entities as core_search_entities
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.types import PrefixName
from ontoloom.selections.store import upsert_entity_selection
from ontoloom.selections.types import SelectionName, WriteMode

from ontoloom_mcp.components.formatting import (
    ToolFilterSource,
    fetch_preview_data,
    format_selection_write,
    format_source,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def search_entities(
    path: OntologyPath,
    into: SelectionName,
    mode: WriteMode = WriteMode.CREATE,
    query: Annotated[str, MinLen(1)] | None = None,
    role: EntityType | None = None,
    namespace: PrefixName | None = None,
    declared: bool | None = None,
    properties: Annotated[list[IRI], MinLen(1)] | None = None,
    within: SelectionName | None = None,
    exclude_deprecated: bool = True,
):
    """Search for entities by name, type, or namespace; save the result as a selection.

    Use `read_selection` to paginate the saved selection, `create_selection` to
    compose it with other selections.

    Args:
    - `into`: Name for the output selection (e.g. `"dogs"`).
    - `mode`: `create` (default) refuses if the selection name already exists; `replace` overwrites it.
    - `query`: Substring match on IRI local names and annotation values (labels, comments).
    - `role`: Filter by entity type: "Class", "ObjectProperty", "DataProperty",
      "AnnotationProperty", "NamedIndividual", "Datatype".
    - `namespace`: Filter by IRI prefix (e.g. "ex", "snomed").
    - `declared`: True = only declared entities, False = only undeclared, None = all.
    - `properties`: Restrict text search to these annotation properties; when query is
      None, find entities that have any annotation with these properties.
    - `within`: Restrict search to a named selection (e.g. `"my_ents"` or
      `"my_axioms"`). An entity selection restricts to those entities; an
      axiom selection restricts to entities mentioned in those axioms.
    - `exclude_deprecated`: Skip deprecated entities (default true).
    """
    props_tuple = tuple(properties or ())

    filters: dict[str, object] = {}
    if query is not None:
        filters["query"] = query
    if role is not None:
        filters["role"] = str(role)
    if namespace is not None:
        filters["namespace"] = namespace
    if declared is not None:
        filters["declared"] = declared
    if props_tuple:
        filters["properties"] = [str(p) for p in props_tuple]

    source = format_source(ToolFilterSource("search_entities", filters, within=within))

    ont = Ontology(path)
    with session(ont) as s:
        iris = core_search_entities(
            s,
            query=query,
            role=role,
            namespace=namespace,
            within=within,
            declared=declared,
            properties=props_tuple,
            exclude_deprecated=exclude_deprecated,
        )

        upserted = upsert_entity_selection(s, into, iris, source, mode=mode)
        preview = fetch_preview_data(s, upserted)
        s.commit()

    return format_selection_write(
        upserted,
        preview,
        no_results=f"No entities found ({source}).",
    )


tool_search_entities = create_tool(
    search_entities,
    name="search_entities",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
