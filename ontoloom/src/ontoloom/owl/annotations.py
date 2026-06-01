from typing import Annotated

from ontoloom.models import FrozenModel
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral, TypedLiteral
from ontoloom.owl.markers import EntityType, Position


class Annotation(FrozenModel):
    """A property-value pair attached to an axiom. Not a standalone axiom."""

    property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.PROPERTY,
    ]

    value: Annotated[
        IRI | TypedLiteral | LangLiteral,
        Position.VALUE,
    ]
