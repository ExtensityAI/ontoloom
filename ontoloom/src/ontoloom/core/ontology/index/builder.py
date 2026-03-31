"""Build an OntologyIndex from an Ontology instance."""

from __future__ import annotations

from ontoloom.core.ontology.models.axioms import AnnotationAssertion
from ontoloom.core.ontology.models.ontology import Ontology

from .extract import extract_from_axiom
from .models import EntityEntry, OntologyIndex


def build_index(ontology: Ontology) -> OntologyIndex:
    index = OntologyIndex()

    for axiom in ontology.axioms:
        for iri, role in extract_from_axiom(axiom):
            entry = index.entities.get(iri)
            if entry is None:
                entry = EntityEntry()
                index.entities[iri] = entry

            if role is not None:
                entry.roles.add(role)
            entry.axioms.append(axiom)

        if isinstance(axiom, AnnotationAssertion):
            entry = index.entities.get(axiom.subject)
            if entry is None:
                entry = EntityEntry()
                index.entities[axiom.subject] = entry
            entry.annotations.append(axiom)

    return index
