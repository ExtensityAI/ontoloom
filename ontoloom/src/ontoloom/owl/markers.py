"""Field-level metadata markers for OWL axiom declarations.

Markers declare OWL-domain facts about Pydantic fields.

`EntityType`, `Position`, and `AxiomTag` enum values are placed *directly* in
`Annotated[]` metadata (no wrapper class). The walker dispatches with
`isinstance(meta, Enum)`. A wrapper around a single enum value would be
indirection without semantic gain.
"""

from dataclasses import dataclass
from enum import StrEnum

from pydantic.fields import FieldInfo

# Field names excluded from an axiom's logical content.
SKIP = ("annotations", "negated")


@dataclass(frozen=True, slots=True)
class Unordered:
    """The field is a tuple whose order has no semantic meaning in OWL."""


class EntityType(StrEnum):
    """The kind of OWL entity an IRI refers to."""

    CLASS = "Class"
    OBJECT_PROPERTY = "ObjectProperty"
    DATA_PROPERTY = "DataProperty"
    ANNOTATION_PROPERTY = "AnnotationProperty"
    NAMED_INDIVIDUAL = "NamedIndividual"
    DATATYPE = "Datatype"


class Position(StrEnum):
    """Structural slot an entity occupies within an axiom's syntactic form."""

    SUB_CLASS = "sub_class"
    SUPER_CLASS = "super_class"

    RESTRICTION_PROPERTY = "restriction_property"
    FILLER = "filler"

    SUB_PROPERTY = "sub_property"
    SUPER_PROPERTY = "super_property"

    CHAIN_MEMBER = "chain_member"

    SUBJECT = "subject"
    PROPERTY = "property"
    VALUE = "value"

    DOMAIN = "domain"
    RANGE = "range"

    SOURCE = "source"
    TARGET = "target"

    INDIVIDUAL = "individual"
    CLASS = "class"

    MEMBER = "member"

    ENTITY = "entity"


type Marker = EntityType | Position | Unordered


def find_marker[T: Marker](info: FieldInfo, marker_type: type[T]) -> T | None:
    return next((m for m in info.metadata if isinstance(m, marker_type)), None)


def is_unordered(info: FieldInfo):
    return find_marker(info, Unordered) is not None
