from pydantic import Field

from ontoloom.core.ontology.models.axioms import Axiom, BaseAxiom
from ontoloom.core.ontology.models.base import FrozenModel
from ontoloom.core.ontology.models.iri import IRI


class Prefix(FrozenModel):
    """A namespace prefix binding."""

    name: str = Field(..., description="Short prefix ('' for default, 'xsd', etc.)")
    iri: str = Field(..., description="Full namespace IRI")


_DEFAULT_PREFIXES = [
    Prefix(name="", iri="http://example.org/ontology#"),
    Prefix(name="owl", iri="http://www.w3.org/2002/07/owl#"),
    Prefix(name="rdf", iri="http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    Prefix(name="rdfs", iri="http://www.w3.org/2000/01/rdf-schema#"),
    Prefix(name="xsd", iri="http://www.w3.org/2001/XMLSchema#"),
]


class Ontology(FrozenModel):
    """An OWL 2 EL ontology — TBox + RBox axioms.

    Does not contain ABox assertions; those live in KnowledgeBase.
    """

    iri: IRI | None = None
    prefixes: list[Prefix] = Field(default_factory=lambda: list(_DEFAULT_PREFIXES))
    axioms: list[Axiom] = Field(default_factory=list)

    def prefix_map(self) -> dict[str, str]:
        return {p.name: p.iri for p in self.prefixes}

    def axioms_of_type[T: BaseAxiom](self, *types: type[T]) -> list[T]:
        return [a for a in self.axioms if isinstance(a, types)]
