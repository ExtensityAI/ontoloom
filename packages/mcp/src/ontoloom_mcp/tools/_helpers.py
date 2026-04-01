from ontoloom.core.ontology.index.models import OntologyIndex
from ontoloom.core.ontology.models.literals import IRI

from ontoloom_mcp.components.search import Scope, search_entities


def format_not_found(iri: IRI, index: OntologyIndex) -> str:
    """Format a not-found message with near-match suggestions."""
    near = search_entities(index.entities, iri.local_name, scope=Scope.IRI, max_results=3)
    suggestion = ""
    if near:
        names = ", ".join(str(r.iri) for r in near)
        suggestion = f" Similar entities: {names}."
    return f"{iri}\nNot found.{suggestion}\nUse `search_entities` to find entities by name."
