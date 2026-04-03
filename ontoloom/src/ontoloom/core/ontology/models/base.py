from enum import StrEnum

from ontoloom.core.ontology.models.literals import Annotation, FrozenModel


class BaseClassExpression(FrozenModel):
    """Base for all OWL 2 EL class expressions."""


class BaseAxiom(FrozenModel):
    """Base for all OWL 2 EL axioms (TBox + RBox + ABox)."""

    annotations: tuple[Annotation, ...] = ()


class EntityType(StrEnum):
    """What kind of OWL entity an IRI represents."""

    CLASS = "Class"
    OBJECT_PROPERTY = "ObjectProperty"
    DATA_PROPERTY = "DataProperty"
    ANNOTATION_PROPERTY = "AnnotationProperty"
    NAMED_INDIVIDUAL = "NamedIndividual"
    DATATYPE = "Datatype"
