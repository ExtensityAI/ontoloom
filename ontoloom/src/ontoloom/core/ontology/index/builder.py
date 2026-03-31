"""Build an OntologyIndex from an Ontology instance."""

from __future__ import annotations

from collections import defaultdict

from ontoloom.core.ontology.models.axioms import AnnotationAssertion
from ontoloom.core.ontology.models.ontology import Ontology

from .extract import extract_from_axiom
from .models import EntityEntry, OntologyIndex


def build_index(ontology: Ontology) -> OntologyIndex:
    entities: defaultdict = defaultdict(EntityEntry)

    for axiom in ontology.axioms:
        for iri, role in extract_from_axiom(axiom):
            entry = entities[iri]
            if role is not None:
                entry.roles.add(role)
            entry.axioms.append(axiom)

        if isinstance(axiom, AnnotationAssertion):
            entities[axiom.subject].annotations.append(axiom)

    return OntologyIndex(entities=dict(entities))
