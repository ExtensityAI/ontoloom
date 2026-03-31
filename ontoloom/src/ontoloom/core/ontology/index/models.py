from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from ontoloom.core.ontology.models.axioms import AnnotationAssertion, Axiom
from ontoloom.core.ontology.models.literals import IRI


class Role(StrEnum):
    """How an IRI is used in the ontology."""

    CLASS = "Class"
    OBJECT_PROPERTY = "ObjectProperty"
    DATA_PROPERTY = "DataProperty"
    INDIVIDUAL = "Individual"
    ANNOTATION_PROPERTY = "AnnotationProperty"


class EntityEntry(BaseModel):
    """Everything known about a single IRI."""

    roles: set[Role] = set()
    axioms: list[Axiom] = []
    annotations: list[AnnotationAssertion] = []


class OntologyIndex(BaseModel):
    """Index over all IRIs in an ontology."""

    entities: dict[IRI, EntityEntry] = {}
