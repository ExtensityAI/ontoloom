from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.models.literals import IRI
from ontoloom.core.ontology.store import OntologyStore

from ontoloom_mcp.components.formatting import format_search_axioms_page
from ontoloom_mcp.components.types import OntologyPath


def _get_axioms(
    path: OntologyPath,
    iri: IRI,
    axiom_types: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Get axioms mentioning an entity. Use `axiom_types` to filter (e.g. `["SubClassOf"]`), and `limit`/`offset` to paginate."""
    with OntologyStore(path) as store:
        page = store.search_by_iri(iri, axiom_types=axiom_types, limit=limit, offset=offset)
        if page.total == 0:
            near = store.search_entities(iri.local_name, scope="iri", limit=3)
            suggestion = ""
            if near:
                names = ", ".join(str(m.iri) for m in near)
                suggestion = f" Similar entities: {names}."
            return f"{iri}\nNo axioms found.{suggestion}\nUse `search_entities` to find entities by name."
        return format_search_axioms_page(page.axioms, page.total, offset)


tool_get_axioms = Tool.from_function(
    _get_axioms,
    name="get_axioms",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
