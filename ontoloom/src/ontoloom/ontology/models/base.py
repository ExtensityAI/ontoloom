from typing import Final

from ontoloom.ontology.models.literals import Annotation, TaggedModel

TYPE_FIELD: Final = "type"
ANNOTATIONS_FIELD: Final = "annotations"


class BaseClassExpression(TaggedModel):
    pass


class BaseAxiom(TaggedModel):
    annotations: tuple[Annotation, ...] = ()
