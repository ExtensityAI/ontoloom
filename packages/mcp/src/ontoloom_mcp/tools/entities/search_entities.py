from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, Session, session
from ontoloom.entities.reader import collect_entity_iris
from ontoloom.entities.reader import search_entities as core_search_entities
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.types import PrefixName
from ontoloom.selections.store import get_selection, upsert_selection
from ontoloom.selections.types import EntitySelectionName, SelectionKind, SelectionRef
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import (
    SELECT_INLINE_MAX,
    SELECT_PREVIEW,
    format_entity_search_page,
    format_selection_result,
)
from ontoloom_mcp.components.locking import format_locked_quoted
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def search_entities(
    path: OntologyPath,
    into: EntitySelectionName,
    query: Annotated[str, MinLen(1)] | None = None,
    role: EntityType | None = None,
    namespace: PrefixName | None = None,
    declared: bool | None = None,
    properties: Annotated[list[IRI], MinLen(1)] | None = None,
    within: SelectionRef | None = None,
    exclude_deprecated: bool = True,
):
    """Search for entities by name, type, or namespace; save the result as a selection.

    Use `read_selection` to paginate the saved selection, `create_selection` to
    compose it with other selections.

    Args:
    - `into`: Kind-prefixed name for the output selection
      (e.g. `"entities:dogs"`).
    - `query`: Substring match on IRI local names and annotation values (labels, comments).
    - `role`: Filter by entity type: "Class", "ObjectProperty", "DataProperty",
      "AnnotationProperty", "NamedIndividual", "Datatype".
    - `namespace`: Filter by IRI prefix (e.g. "ex", "snomed").
    - `declared`: True = only declared entities, False = only undeclared, None = all.
    - `properties`: Restrict text search to these annotation properties; when query is
      None, find entities that have any annotation with these properties.
    - `within`: Restrict search to a named selection (e.g. `"entities:my_ents"`
      or `"axioms:my_axioms"`). An entity selection restricts to those entities;
      an axiom selection restricts to entities mentioned in those axioms.
    - `exclude_deprecated`: Skip deprecated entities (default true).
    """
    ont = Ontology(path)
    with session(ont) as s:
        kwargs = {
            "query": query,
            "role": role,
            "namespace": namespace,
            "within": within,
            "declared": declared,
            "properties": properties or (),
            "exclude_deprecated": exclude_deprecated,
        }

        iris = collect_entity_iris(s, **kwargs)
        source = _build_source(query, role, namespace, declared, properties, within)
        upserted = upsert_selection(s, into.bare, SelectionKind.ENTITIES, iris, source)
        sel = upserted.selection

        if not iris:
            no_results = _no_results_msg(query, role, namespace, declared, properties, within)
            s.commit()
            return f"0 entities -> {format_locked_quoted(sel)}.\n{no_results}"

        limit_n = sel.size if sel.size <= SELECT_INLINE_MAX else SELECT_PREVIEW
        page = core_search_entities(s, **kwargs, limit=limit_n, offset=0)
        page_text = format_entity_search_page(page)

        result = format_selection_result("entities", upserted, page_text)

        if within is not None:
            result += "\n" + _within_metadata(s, within)

        s.commit()

    return result


def _within_metadata(s: Session, within: SelectionRef):
    sel = get_selection(s, within.bare)
    return f"\nWithin selection {format_locked_quoted(sel)} ({sel.kind}, {sel.size} items)"


def _filter_parts(query, role, namespace, declared, properties, within) -> list[str]:
    parts = []
    if query:
        parts.append(f"query={dquoted(query)}")
    if role:
        parts.append(f"role={dquoted(role)}")
    if namespace:
        parts.append(f"namespace={dquoted(namespace)}")
    if declared is not None:
        parts.append(f"declared={declared}")
    if properties:
        parts.append(f"properties=[{', '.join(dquoted(p) for p in properties)}]")
    if within is not None:
        parts.append(f"within={dquoted(str(within))}")
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
