from mcp.types import ToolAnnotations
from ontoloom.ontology import entities, selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.literals import IRI, EntityType
from ontoloom.ontology.types import SelectionKind

from ontoloom_mcp.components.formatting import (
    SELECT_INLINE_MAX,
    SELECT_PREVIEW,
    format_entity_search_page,
    format_selection_result,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, PrefixName, SelectionName


def search_entities(
    path: OntologyPath,
    into: SelectionName,
    query: str | None = None,
    role: EntityType | None = None,
    namespace: PrefixName | None = None,
    declared: bool | None = None,
    properties: list[IRI] | None = None,
    within: SelectionName | None = None,
    exclude_deprecated: bool = True,
) -> str:
    """Search for entities by name, type, or namespace. Results are saved as a named
    selection. Use `read_selection` to paginate, `create_selection` to compose with
    other selections.

    - `into`: Name for the output selection (required).
    - `query`: Substring match on IRI local names and annotation values (labels, comments).
    - `role`: Filter by entity type: "Class", "ObjectProperty", "DataProperty",
      "AnnotationProperty", "NamedIndividual", "Datatype".
    - `namespace`: Filter by IRI prefix (e.g. "ex", "snomed").
    - `declared`: True = only declared entities, False = only undeclared, None = all.
    - `properties`: Restrict text search to these annotation properties; when query is
      None, find entities that have any annotation with these properties.
    - `within`: Restrict search to a named selection. An entity selection restricts to
      those entities; an axiom selection restricts to entities mentioned in those axioms.
    - `exclude_deprecated`: Skip deprecated entities (default true).
    """
    with Ontology(path) as ont:
        kwargs = {
            "query": query,
            "role": role,
            "namespace": namespace,
            "within": within,
            "declared": declared,
            "properties": properties,
            "exclude_deprecated": exclude_deprecated,
        }

        iris = entities.collect_iris(ont, **kwargs)
        source = _build_source(query, role, namespace, declared, properties, within)
        content_hash, cardinality, old_cardinality = selections.write(
            ont, into, SelectionKind.ENTITIES, iris, source
        )

        if not iris:
            no_results = _no_results_msg(query, role, namespace, declared, properties, within)
            return f"0 entities \u2192 {into!r} (sel@{content_hash}).\n{no_results}"

        limit_n = cardinality if cardinality <= SELECT_INLINE_MAX else SELECT_PREVIEW
        page = entities.search(ont, **kwargs, limit=limit_n, offset=0)
        page_text = format_entity_search_page(page.matches, cardinality, 0)

        result = format_selection_result(
            "entities", into, content_hash, cardinality, old_cardinality, page_text
        )

        if within is not None:
            result += "\n" + _within_metadata(ont, within)

        return result


def _within_metadata(ont: Ontology, within: str):
    sel = selections.get_info(ont, within)
    return f"\nWithin selection {sel.name!r} ({sel.kind}, {sel.cardinality} items, sel@{sel.hash})"


def _no_results_msg(query, role, namespace, declared, properties, within):
    parts = []
    if query:
        parts.append(f"query={query!r}")
    if role:
        parts.append(f"role={role}")
    if namespace:
        parts.append(f"namespace={namespace}")
    if declared is not None:
        parts.append(f"declared={declared}")
    if properties:
        parts.append(f"properties={properties}")
    if within:
        parts.append(f"within={within!r}")
    filter_desc = ", ".join(parts) if parts else "no filters"
    return f"No entities found ({filter_desc})."


def _build_source(query, role, namespace, declared, properties, within):
    parts = []
    if query:
        parts.append(f"query={query!r}")
    if role:
        parts.append(f"role={role!r}")
    if namespace:
        parts.append(f"namespace={namespace!r}")
    if declared is not None:
        parts.append(f"declared={declared}")
    if properties:
        parts.append(f"properties={properties}")
    if within:
        parts.append(f"within={within!r}")
    return f"search_entities({', '.join(parts)})"


tool_search_entities = create_tool(
    search_entities,
    name="search_entities",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
