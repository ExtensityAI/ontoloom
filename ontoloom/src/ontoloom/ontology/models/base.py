from enum import StrEnum

from ontoloom.ontology.models.literals import Annotation, FrozenModel


class BaseClassExpression(FrozenModel):
    pass


class BaseAxiom(FrozenModel):
    annotations: tuple[Annotation, ...] = ()


class EntityType(StrEnum):
    CLASS = "Class"
    OBJECT_PROPERTY = "ObjectProperty"
    DATA_PROPERTY = "DataProperty"
    ANNOTATION_PROPERTY = "AnnotationProperty"
    NAMED_INDIVIDUAL = "NamedIndividual"
    DATATYPE = "Datatype"
