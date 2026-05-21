import functools
import operator
from enum import StrEnum
from typing import Annotated, Literal, override

from pydantic import Field, model_validator

from ontoloom.models import FrozenModel, make_tag_resolver, tagged, tagged_union_meta
from ontoloom.owl._render import format_owl_struct
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.expressions import ClassExpression
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import (
    DataRange,
    LangLiteral,
    LiteralValue,
    TypedLiteral,
)
from ontoloom.owl.markers import EntityType, Position, Unordered


class BaseAxiom(FrozenModel):
    annotations: tuple[Annotation, ...] = ()

    @override
    def __str__(self) -> str:
        return format_owl_struct(self)


# -- Annotation axioms --


class AnnotationAssertion(BaseAxiom):
    """An annotation on an entity. No logical semantics.

    AnnotationAssertion(rdfs:label, :Dog, "Dog"@en)
    """

    property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.PROPERTY,
    ]
    subject: Annotated[IRI, Position.SUBJECT]
    value: Annotated[
        IRI | TypedLiteral | LangLiteral,
        Position.VALUE,
    ]


# -- TBox: class axioms --


class SubClassOf(BaseAxiom):
    """C ⊑ D -> every instance of sub_class is an instance of super_class.

    SubClassOf(Dog, Animal)
        -> every dog is an animal
    SubClassOf(Mammal, ∃hasPart.Lung)
        -> every mammal has some lung
    """

    sub_class: Annotated[ClassExpression, Position.SUB_CLASS]
    super_class: Annotated[ClassExpression, Position.SUPER_CLASS]


class EquivalentClasses(BaseAxiom):
    """C ≡ D -> classes have exactly the same instances.

    Use only for true definitions (necessary AND sufficient).

    EquivalentClasses(Mother, Woman ⊓ Parent)
    """

    equivalent_classes: Annotated[
        tuple[ClassExpression, ...],
        Unordered(),
        Position.MEMBER,
        Field(min_length=2),
    ]


class DisjointClasses(BaseAxiom):
    """Classes share no instances.

    DisjointClasses(Male, Female) -> nothing is both male and female
    """

    disjoint_classes: Annotated[
        tuple[ClassExpression, ...],
        Unordered(),
        Position.MEMBER,
        Field(min_length=2),
    ]


# -- RBox: object property axioms --


class SubObjectPropertyOf(BaseAxiom):
    """r ⊑ s -> if r(x,y) then s(x,y).

    SubObjectPropertyOf(hasMother, hasParent)
    """

    sub_object_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.SUB_PROPERTY,
    ]
    super_object_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.SUPER_PROPERTY,
    ]


class SubObjectPropertyOfChain(BaseAxiom):
    """r₁ ∘ r₂ ∘ ... ∘ rₙ ⊑ s -> property chain.

    Regularity condition must hold. Stick to length-2 chains.

    SubObjectPropertyOfChain([hasParent, hasBrother], hasUncle)
    SubObjectPropertyOfChain([partOf, partOf], partOf)  -> transitivity
    """

    chain: Annotated[
        tuple[IRI, ...],
        EntityType.OBJECT_PROPERTY,
        Position.CHAIN_MEMBER,
        Field(min_length=2),
    ]
    super_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.SUPER_PROPERTY,
    ]


class EquivalentObjectProperties(BaseAxiom):
    """r₁ ≡ r₂ -> properties relate the same pairs of individuals."""

    object_properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.OBJECT_PROPERTY,
        Position.MEMBER,
        Field(min_length=2),
    ]


class TransitiveObjectProperty(BaseAxiom):
    """r(x,y) ∧ r(y,z) -> r(x,z)

    Equivalent to SubObjectPropertyOfChain([r, r], r).
    """

    transitive_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ]


class ReflexiveObjectProperty(BaseAxiom):
    """r(x,x) for every individual x.

    ReflexiveObjectProperty(partOf) -> everything is part of itself
    """

    reflexive_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ]


class ObjectPropertyDomain(BaseAxiom):
    """If x is related to anything by r, then x is in C.

    This is an inference rule, not documentation.
    If you assert r(x, y), the reasoner infers x ∈ C.
    """

    object_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ]
    domain: Annotated[ClassExpression, Position.DOMAIN]


class ObjectPropertyRange(BaseAxiom):
    """If anything is related to y by r, then y ∈ C.

    Same caution as domain -> this triggers inferences.
    """

    object_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ]
    range: Annotated[ClassExpression, Position.RANGE]


# -- RBox: data property axioms --


class SubDataPropertyOf(BaseAxiom):
    """dp₁ ⊑ dp₂ -> if dp₁(x,v) then dp₂(x,v)."""

    sub_data_property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.SUB_PROPERTY,
    ]
    super_data_property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.SUPER_PROPERTY,
    ]


class EquivalentDataProperties(BaseAxiom):
    """dp₁ ≡ dp₂ -> data properties have the same values for all individuals."""

    data_properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.DATA_PROPERTY,
        Position.MEMBER,
        Field(min_length=2),
    ]


class DataPropertyDomain(BaseAxiom):
    """If x has any value for dp, then x ∈ C."""

    data_property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
    ]
    domain: Annotated[ClassExpression, Position.DOMAIN]


class DataPropertyRange(BaseAxiom):
    """All values of dp fall within this data range."""

    data_property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
    ]
    range: Annotated[DataRange, Position.RANGE]


class FunctionalDataProperty(BaseAxiom):
    """dp has at most one value per individual.

    FunctionalDataProperty(hasAge) -> each thing has at most one age
    """

    functional_property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
    ]


# -- Annotation property axioms --


class SubAnnotationPropertyOf(BaseAxiom):
    sub_annotation_property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.SUB_PROPERTY,
    ]
    super_annotation_property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.SUPER_PROPERTY,
    ]


class AnnotationPropertyDomain(BaseAxiom):
    """No logical semantics."""

    annotation_property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.PROPERTY,
    ]
    domain: Annotated[IRI, Position.DOMAIN]


class AnnotationPropertyRange(BaseAxiom):
    """No logical semantics."""

    annotation_property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.PROPERTY,
    ]
    range: Annotated[IRI, Position.RANGE]


# -- Schema axioms --


class HasKey(BaseAxiom):
    """Instances of CE are uniquely identified by the listed properties.

    HasKey(Person, [hasSSN]) -> SSN uniquely identifies a person
    """

    class_expression: Annotated[ClassExpression, Position.CLASS]
    object_properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ] = ()
    data_properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
    ] = ()

    @model_validator(mode="after")
    def _check_has_properties(self):
        if not self.object_properties and not self.data_properties:
            msg = "HasKey must have at least one object or data property"
            raise ValueError(msg)
        return self


class DatatypeDefinition(BaseAxiom):
    datatype: Annotated[
        IRI,
        EntityType.DATATYPE,
        Position.ENTITY,
    ]
    data_range: Annotated[DataRange, Position.RANGE]


class Declaration(BaseAxiom):
    entity_type: EntityType
    iri: Annotated[IRI, Position.ENTITY]


# -- ABox: assertions --


class ClassAssertion(BaseAxiom):
    """a ∈ C -> individual a is an instance of C.

    ClassAssertion(Dog, Fido)
    """

    class_expression: Annotated[ClassExpression, Position.CLASS]
    individual: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.INDIVIDUAL]


class ObjectPropertyAssertion(BaseAxiom):
    """r(a, b) -> a is related to b by r.

    ObjectPropertyAssertion(owns, Alice, Fido)
    """

    property: Annotated[IRI, EntityType.OBJECT_PROPERTY, Position.PROPERTY]
    source: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.SOURCE]
    target: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.TARGET]


class NegativeObjectPropertyAssertion(BaseAxiom):
    """¬r(a, b) -> a is NOT related to b by r.

    NegativeObjectPropertyAssertion(owns, Alice, Rex)
    """

    property: Annotated[IRI, EntityType.OBJECT_PROPERTY, Position.PROPERTY]
    source: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.SOURCE]
    target: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.TARGET]
    negated: Literal[True] = True


class DataPropertyAssertion(BaseAxiom):
    """dp(a, v) -> a has value v for dp.

    DataPropertyAssertion(hasAge, Alice, "30"^^xsd:integer)
    """

    property: Annotated[IRI, EntityType.DATA_PROPERTY, Position.PROPERTY]
    individual: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.INDIVIDUAL]
    value: LiteralValue


class NegativeDataPropertyAssertion(BaseAxiom):
    """¬dp(a, v) -> a does NOT have value v for dp.

    NegativeDataPropertyAssertion(hasAge, Alice, "99"^^xsd:integer)
    """

    property: Annotated[IRI, EntityType.DATA_PROPERTY, Position.PROPERTY]
    individual: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.INDIVIDUAL]
    value: LiteralValue
    negated: Literal[True] = True


class SameIndividual(BaseAxiom):
    """a = b -> both IRIs denote the same entity."""

    same_individuals: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.NAMED_INDIVIDUAL,
        Position.MEMBER,
        Field(min_length=2),
    ]


class DifferentIndividuals(BaseAxiom):
    """a ≠ b -> all listed individuals are pairwise distinct."""

    different_individuals: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.NAMED_INDIVIDUAL,
        Position.MEMBER,
        Field(min_length=2),
    ]


# -- Discriminated union of all axiom types --


AXIOM_CLASSES = (
    AnnotationAssertion,
    SubClassOf,
    EquivalentClasses,
    DisjointClasses,
    SubObjectPropertyOf,
    SubObjectPropertyOfChain,
    EquivalentObjectProperties,
    TransitiveObjectProperty,
    ReflexiveObjectProperty,
    ObjectPropertyDomain,
    ObjectPropertyRange,
    SubDataPropertyOf,
    EquivalentDataProperties,
    DataPropertyDomain,
    DataPropertyRange,
    FunctionalDataProperty,
    SubAnnotationPropertyOf,
    AnnotationPropertyDomain,
    AnnotationPropertyRange,
    HasKey,
    DatatypeDefinition,
    Declaration,
    ClassAssertion,
    ObjectPropertyAssertion,
    NegativeObjectPropertyAssertion,
    DataPropertyAssertion,
    NegativeDataPropertyAssertion,
    SameIndividual,
    DifferentIndividuals,
)


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


_TAGS = frozenset(t.value for t in AxiomTag)
_CLASS_NAMES = frozenset(cls.__name__ for cls in AXIOM_CLASSES)
if _TAGS != _CLASS_NAMES:
    _missing = _CLASS_NAMES - _TAGS
    _extra = _TAGS - _CLASS_NAMES
    msg = f"AxiomTag/AXIOM_CLASSES drift — missing tags: {_missing}; extra tags: {_extra}"
    raise RuntimeError(msg)


_get_axiom_tag = make_tag_resolver(AXIOM_CLASSES, union_name="Axiom")

Axiom = Annotated[
    functools.reduce(operator.or_, (tagged(c) for c in AXIOM_CLASSES)),
    *tagged_union_meta(_get_axiom_tag),
]
