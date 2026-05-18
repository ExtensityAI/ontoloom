"""Field-level metadata markers for OWL axiom declarations.

Markers declare OWL-domain facts about Pydantic fields. Read by canonical
normalization, entity extraction, pattern matching, and codegen.

`EntityType`, `Position`, and `AxiomTag` enum values are placed *directly* in
`Annotated[]` metadata (no wrapper class). The walker dispatches with
`isinstance(meta, Enum)`. A wrapper around a single enum value would be
indirection without semantic gain.
"""

from dataclasses import dataclass
from enum import StrEnum

from pydantic.fields import FieldInfo


@dataclass(frozen=True, slots=True)
class Unordered:
    """The field is a tuple whose order has no semantic meaning in OWL.

    Read by canonical normalization (sorts), pattern matching (permutes),
    and pattern codegen (allows partial-set Contains in generated patterns).
    """


class EntityType(StrEnum):
    """The kind of OWL entity an IRI refers to."""

    CLASS = "Class"
    OBJECT_PROPERTY = "ObjectProperty"
    DATA_PROPERTY = "DataProperty"
    ANNOTATION_PROPERTY = "AnnotationProperty"
    NAMED_INDIVIDUAL = "NamedIndividual"
    DATATYPE = "Datatype"


class AxiomTag(StrEnum):
    """Structural tag for an OWL axiom — matches the axiom class's `__name__`.

    Stored in `axioms.type` and used as the discriminator in `WithTypes`.
    """

    ANNOTATION_ASSERTION = "AnnotationAssertion"
    SUB_CLASS_OF = "SubClassOf"
    EQUIVALENT_CLASSES = "EquivalentClasses"
    DISJOINT_CLASSES = "DisjointClasses"
    SUB_OBJECT_PROPERTY_OF = "SubObjectPropertyOf"
    SUB_OBJECT_PROPERTY_OF_CHAIN = "SubObjectPropertyOfChain"
    EQUIVALENT_OBJECT_PROPERTIES = "EquivalentObjectProperties"
    TRANSITIVE_OBJECT_PROPERTY = "TransitiveObjectProperty"
    REFLEXIVE_OBJECT_PROPERTY = "ReflexiveObjectProperty"
    OBJECT_PROPERTY_DOMAIN = "ObjectPropertyDomain"
    OBJECT_PROPERTY_RANGE = "ObjectPropertyRange"
    SUB_DATA_PROPERTY_OF = "SubDataPropertyOf"
    EQUIVALENT_DATA_PROPERTIES = "EquivalentDataProperties"
    DATA_PROPERTY_DOMAIN = "DataPropertyDomain"
    DATA_PROPERTY_RANGE = "DataPropertyRange"
    FUNCTIONAL_DATA_PROPERTY = "FunctionalDataProperty"
    SUB_ANNOTATION_PROPERTY_OF = "SubAnnotationPropertyOf"
    ANNOTATION_PROPERTY_DOMAIN = "AnnotationPropertyDomain"
    ANNOTATION_PROPERTY_RANGE = "AnnotationPropertyRange"
    HAS_KEY = "HasKey"
    DATATYPE_DEFINITION = "DatatypeDefinition"
    DECLARATION = "Declaration"
    CLASS_ASSERTION = "ClassAssertion"
    OBJECT_PROPERTY_ASSERTION = "ObjectPropertyAssertion"
    NEGATIVE_OBJECT_PROPERTY_ASSERTION = "NegativeObjectPropertyAssertion"
    DATA_PROPERTY_ASSERTION = "DataPropertyAssertion"
    NEGATIVE_DATA_PROPERTY_ASSERTION = "NegativeDataPropertyAssertion"
    SAME_INDIVIDUAL = "SameIndividual"
    DIFFERENT_INDIVIDUALS = "DifferentIndividuals"


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
