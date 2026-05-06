from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.entities.store import collect_entity_iris
from ontoloom.entities.store import search_entities as core_search_entities
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.selections.store import get_selection, upsert_selection
from ontoloom.selections.types import SelectionKind

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
):
    """Search for entities by name, type, or namespace; save the result as a selection.

    Use `read_selection` to paginate the saved selection, `create_selection` to
    compose it with other selections.

    Args:
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

        iris = collect_entity_iris(ont, **kwargs)
        source = _build_source(query, role, namespace, declared, properties, within)
        upserted = upsert_selection(ont, into, SelectionKind.ENTITIES, iris, source)
        sel = upserted.selection

        if not iris:
            no_results = _no_results_msg(query, role, namespace, declared, properties, within)
            return f"0 entities -> {sel.locked!r}.\n{no_results}"

        limit_n = sel.size if sel.size <= SELECT_INLINE_MAX else SELECT_PREVIEW
        page = core_search_entities(ont, **kwargs, limit=limit_n, offset=0)
        page_text = format_entity_search_page(page.matches, sel.size, 0)

        result = format_selection_result("entities", upserted, page_text)

        if within is not None:
            result += "\n" + _within_metadata(ont, within)

        return result


def _within_metadata(ont: Ontology, within: str):
    sel = get_selection(ont, within)
    return f"\nWithin selection {sel.locked!r} ({sel.kind}, {sel.size} items)"


def _filter_parts(query, role, namespace, declared, properties, within) -> list[str]:
    parts = []
    if query:
        parts.append(f"query={query!r}")
    if role:
        parts.append(f"role={str(role)!r}")
    if namespace:
        parts.append(f"namespace={str(namespace)!r}")
    if declared is not None:
        parts.append(f"declared={declared}")
    if properties:
        parts.append(f"properties=[{', '.join(repr(str(p)) for p in properties)}]")
    if within:
        parts.append(f"within={str(within)!r}")
    return parts


def _no_results_msg(query, role, namespace, declared, properties, within):
    parts = _filter_parts(query, role, namespace, declared, properties, within)
    desc = ", ".join(parts) if parts else "no filters"
    return f"No entities found ({desc})."


def _build_source(query, role, namespace, declared, properties, within):
    parts = _filter_parts(query, role, namespace, declared, properties, within)
    return f"search_entities({', '.join(parts)})"


tool_search_entities = create_tool(
    search_entities,
    name="search_entities",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
