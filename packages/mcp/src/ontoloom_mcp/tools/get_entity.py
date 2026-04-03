from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.models.literals import IRI
from ontoloom.core.ontology.store import OntologyStore

from ontoloom_mcp.components.formatting import format_entity_inspect
from ontoloom_mcp.components.types import OntologyPath


def _get_entity(path: OntologyPath, iri: IRI):
    """Get details for a single entity: roles, annotations, and asserted axiom counts by type.

    Does NOT include inherited or inferred information.
    Use `search_axioms` to see the full axiom details.
    """
    with OntologyStore(path) as store:
        info = store.get_entity(iri)
        if info is None:
            near = store.search_entities(query=iri.local_name, limit=3)
            suggestion = ""
            if near.matches:
                names = ", ".join(str(m.iri) for m in near.matches)
                suggestion = f" Similar entities: {names}."
            return f"{iri}\nNot found.{suggestion}\nUse `search_entities` to find entities by name."
        return format_entity_inspect(iri, info)


tool_get_entity = Tool.from_function(
    _get_entity,
    name="get_entity",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
