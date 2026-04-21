from typing import Literal

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.formatting import format_entity_search_page
from ontoloom_mcp.components.types import OntologyPath

Role = Literal[
    "Class",
    "ObjectProperty",
    "DataProperty",
    "AnnotationProperty",
    "NamedIndividual",
    "Datatype",
]

_SELECT_PREVIEW = 5
_SELECT_INLINE_MAX = 20


@handle_tool_errors
def _search_entities(
    path: OntologyPath,
    query: str = "",
    role: Role | str = "",
    namespace: str = "",
    within: str = "",
    select: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """Search and filter entities. All parameters optional — no filters lists all entities.

    - `query`: Substring match on IRI local names and annotation values (labels, comments).
    - `role`: Filter by entity type: "Class", "ObjectProperty", "DataProperty",
      "AnnotationProperty", "NamedIndividual", "Datatype".
    - `namespace`: Filter by IRI prefix (e.g. "ex", "snomed").
    - `within`: Scope search to an existing selection (name only). If kind='entities',
      restricts to those specific entities (further filter). If kind='axioms', restricts
      to entities mentioned in those axioms.
    - `select`: Save ALL matching entity IRIs to a selection with this name.
      Incompatible with limit/offset. Use `read_selection` to paginate saved results.
    - `limit`/`offset`: Pagination (incompatible with `select`).
    """
    if select and "@" in select:
        msg = "Selection names must not contain '@'."
        raise ValueError(msg)
    if select and (limit != 50 or offset != 0):
        msg = "limit/offset are incompatible with select. Use read_selection to paginate saved results."
        raise ValueError(msg)

    with OntologyStore(path) as store:
        kwargs = {
            "query": query or None,
            "role": role or None,
            "namespace": namespace or None,
            "within": within or None,
        }

        if select:
            # Collect all IRIs and save to selection
            iris = store.collect_entity_iris(**kwargs)
            if not iris:
                return _no_results_msg(query, role, namespace, within)

            source = _build_source(query, role, namespace, within)
            content_hash, cardinality, old_cardinality = store._write_selection(
                select, "entities", iris, source
            )

            parts = [f"{cardinality} entities \u2192 {select!r} (sel@{content_hash})."]
            if old_cardinality is not None:
                parts.append(f"Overwrote previous ({old_cardinality} items).")

            if cardinality <= _SELECT_INLINE_MAX:
                page = store.search_entities(**kwargs, limit=cardinality, offset=0)
                parts.append("")
                parts.append(format_entity_search_page(page.matches, page.total, 0))
            else:
                page = store.search_entities(**kwargs, limit=_SELECT_PREVIEW, offset=0)
                parts.append(f"Preview (first {_SELECT_PREVIEW}):")
                parts.append("")
                parts.append(format_entity_search_page(page.matches, cardinality, 0))
                parts.append(
                    f"\nUse read_selection(name={select!r}) to browse all {cardinality} results."
                )

            return "\n".join(parts)

        # Normal paginated search
        page = store.search_entities(**kwargs, limit=limit, offset=offset)
        if page.total == 0:
            return _no_results_msg(query, role, namespace, within)
        return format_entity_search_page(page.matches, page.total, offset)


def _no_results_msg(query, role, namespace, within):
    parts = []
    if query:
        parts.append(f"query={query!r}")
    if role:
        parts.append(f"role={role}")
    if namespace:
        parts.append(f"namespace={namespace}")
    if within:
        parts.append(f"within={within!r}")
    filter_desc = ", ".join(parts) if parts else "no filters"
    return f"No entities found ({filter_desc})."


def _build_source(query, role, namespace, within):
    parts = []
    if query:
        parts.append(f"query={query!r}")
    if role:
        parts.append(f"role={role!r}")
    if namespace:
        parts.append(f"namespace={namespace!r}")
    if within:
        parts.append(f"within={within!r}")
    return f"search_entities({', '.join(parts)})"


tool_search_entities = Tool.from_function(
    _search_entities,
    name="search_entities",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
