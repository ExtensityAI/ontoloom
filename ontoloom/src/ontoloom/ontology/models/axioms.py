from typing import Annotated, Literal, override

from pydantic import Field, model_validator

from ontoloom.ontology.models.assertions import (
    ClassAssertion,
    DataPropertyAssertion,
    DifferentIndividuals,
    NegativeDataPropertyAssertion,
    NegativeObjectPropertyAssertion,
    ObjectPropertyAssertion,
    SameIndividual,
)
from ontoloom.ontology.models.base import BaseAxiom
from ontoloom.ontology.models.expressions import ClassExpression
from ontoloom.ontology.models.literals import (
    IRI,
    DataRange,
    EntityType,
    LangLiteral,
    Position,
    TypedLiteral,
)
from ontoloom.ontology.models.markers import EntityKind, EntityPosition, Unordered


class AnnotationAssertion(BaseAxiom):
    """An annotation on an entity. No logical semantics.

    AnnotationAssertion(rdfs:label, :Dog, "Dog"@en)
    """

    type: Literal["AnnotationAssertion"] = "AnnotationAssertion"
    property: Annotated[
        IRI,
        EntityKind(EntityType.ANNOTATION_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]
    subject: Annotated[IRI, EntityPosition(Position.SUBJECT)]
    value: Annotated[
        IRI | TypedLiteral | LangLiteral,
        EntityPosition(Position.VALUE),
    ]

    @override
    def __str__(self) -> str:
        return f"AnnotationAssertion({self.property}, {self.subject}, {self.value})"


class SubClassOf(BaseAxiom):
    """C ⊑ D — every instance of sub_class is an instance of super_class.

    SubClassOf(Dog, Animal)
        -> every dog is an animal
    SubClassOf(Mammal, ∃hasPart.Lung)
        -> every mammal has some lung
    """

    type: Literal["SubClassOf"] = "SubClassOf"
    sub_class: Annotated[ClassExpression, EntityPosition(Position.SUB_CLASS)]
    super_class: Annotated[ClassExpression, EntityPosition(Position.SUPER_CLASS)]

    @override
    def __str__(self) -> str:
        return f"SubClassOf({self.sub_class}, {self.super_class})"


class EquivalentClasses(BaseAxiom):
    """C ≡ D — classes have exactly the same instances.

    Use only for true definitions (necessary AND sufficient).

    EquivalentClasses(Mother, Woman ⊓ Parent)
    """

    type: Literal["EquivalentClasses"] = "EquivalentClasses"
    expressions: Annotated[
        tuple[ClassExpression, ...],
        Unordered(),
        EntityPosition(Position.MEMBER),
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"EquivalentClasses({', '.join(str(e) for e in self.expressions)})"


class DisjointClasses(BaseAxiom):
    """Classes share no instances.

    DisjointClasses(Male, Female) -> nothing is both male and female
    """

    type: Literal["DisjointClasses"] = "DisjointClasses"
    expressions: Annotated[
        tuple[ClassExpression, ...],
        Unordered(),
        EntityPosition(Position.MEMBER),
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"DisjointClasses({', '.join(str(e) for e in self.expressions)})"


class SubObjectPropertyOf(BaseAxiom):
    """r ⊑ s — if r(x,y) then s(x,y).

    SubObjectPropertyOf(hasMother, hasParent)
    """

    type: Literal["SubObjectPropertyOf"] = "SubObjectPropertyOf"
    sub_property: Annotated[
        IRI,
        EntityKind(EntityType.OBJECT_PROPERTY),
        EntityPosition(Position.SUB_PROPERTY),
    ]
    super_property: Annotated[
        IRI,
        EntityKind(EntityType.OBJECT_PROPERTY),
        EntityPosition(Position.SUPER_PROPERTY),
    ]

    @override
    def __str__(self) -> str:
        return f"SubObjectPropertyOf({self.sub_property}, {self.super_property})"


class SubObjectPropertyOfChain(BaseAxiom):
    """r₁ ∘ r₂ ∘ ... ∘ rₙ ⊑ s — property chain.

    Regularity condition must hold. Stick to length-2 chains.

    SubObjectPropertyOfChain([hasParent, hasBrother], hasUncle)
    SubObjectPropertyOfChain([partOf, partOf], partOf)  — transitivity
    """

    type: Literal["SubObjectPropertyOfChain"] = "SubObjectPropertyOfChain"
    chain: Annotated[
        tuple[IRI, ...],
        EntityKind(EntityType.OBJECT_PROPERTY),
        EntityPosition(Position.CHAIN_MEMBER),
        Field(min_length=2),
    ]
    super_property: Annotated[
        IRI,
        EntityKind(EntityType.OBJECT_PROPERTY),
        EntityPosition(Position.SUPER_PROPERTY),
    ]

    @override
    def __str__(self) -> str:
        chain = ", ".join(str(p) for p in self.chain)
        return f"SubObjectPropertyOfChain([{chain}], {self.super_property})"


class EquivalentObjectProperties(BaseAxiom):
    """r₁ ≡ r₂ — properties relate the same pairs of individuals."""

    type: Literal["EquivalentObjectProperties"] = "EquivalentObjectProperties"
    properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityKind(EntityType.OBJECT_PROPERTY),
        EntityPosition(Position.MEMBER),
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"EquivalentObjectProperties({', '.join(str(p) for p in self.properties)})"


class TransitiveObjectProperty(BaseAxiom):
    """r(x,y) ∧ r(y,z) -> r(x,z)

    Equivalent to SubObjectPropertyOfChain([r, r], r).
    """

    type: Literal["TransitiveObjectProperty"] = "TransitiveObjectProperty"
    property: Annotated[
        IRI,
        EntityKind(EntityType.OBJECT_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]

    @override
    def __str__(self) -> str:
        return f"TransitiveObjectProperty({self.property})"


class ReflexiveObjectProperty(BaseAxiom):
    """r(x,x) for every individual x.

    ReflexiveObjectProperty(partOf) — everything is part of itself
    """

    type: Literal["ReflexiveObjectProperty"] = "ReflexiveObjectProperty"
    property: Annotated[
        IRI,
        EntityKind(EntityType.OBJECT_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]

    @override
    def __str__(self) -> str:
        return f"ReflexiveObjectProperty({self.property})"


class ObjectPropertyDomain(BaseAxiom):
    """If x is related to anything by r, then x is in C.

    This is an inference rule, not documentation.
    If you assert r(x, y), the reasoner infers x ∈ C.
    """

    type: Literal["ObjectPropertyDomain"] = "ObjectPropertyDomain"
    property: Annotated[
        IRI,
        EntityKind(EntityType.OBJECT_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]
    domain: Annotated[ClassExpression, EntityPosition(Position.DOMAIN)]

    @override
    def __str__(self) -> str:
        return f"ObjectPropertyDomain({self.property}, {self.domain})"


class ObjectPropertyRange(BaseAxiom):
    """If anything is related to y by r, then y ∈ C.

    Same caution as domain — this triggers inferences.
    """

    type: Literal["ObjectPropertyRange"] = "ObjectPropertyRange"
    property: Annotated[
        IRI,
        EntityKind(EntityType.OBJECT_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]
    range: Annotated[ClassExpression, EntityPosition(Position.RANGE)]

    @override
    def __str__(self) -> str:
        return f"ObjectPropertyRange({self.property}, {self.range})"


class SubDataPropertyOf(BaseAxiom):
    """dp₁ ⊑ dp₂ — if dp₁(x,v) then dp₂(x,v)."""

    type: Literal["SubDataPropertyOf"] = "SubDataPropertyOf"
    sub_property: Annotated[
        IRI,
        EntityKind(EntityType.DATA_PROPERTY),
        EntityPosition(Position.SUB_PROPERTY),
    ]
    super_property: Annotated[
        IRI,
        EntityKind(EntityType.DATA_PROPERTY),
        EntityPosition(Position.SUPER_PROPERTY),
    ]

    @override
    def __str__(self) -> str:
        return f"SubDataPropertyOf({self.sub_property}, {self.super_property})"


class EquivalentDataProperties(BaseAxiom):
    """dp₁ ≡ dp₂ — data properties have the same values for all individuals."""

    type: Literal["EquivalentDataProperties"] = "EquivalentDataProperties"
    properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityKind(EntityType.DATA_PROPERTY),
        EntityPosition(Position.MEMBER),
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"EquivalentDataProperties({', '.join(str(p) for p in self.properties)})"


class DataPropertyDomain(BaseAxiom):
    """If x has any value for dp, then x ∈ C."""

    type: Literal["DataPropertyDomain"] = "DataPropertyDomain"
    property: Annotated[
        IRI,
        EntityKind(EntityType.DATA_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]
    domain: Annotated[ClassExpression, EntityPosition(Position.DOMAIN)]

    @override
    def __str__(self) -> str:
        return f"DataPropertyDomain({self.property}, {self.domain})"


class DataPropertyRange(BaseAxiom):
    """All values of dp fall within this data range."""

    type: Literal["DataPropertyRange"] = "DataPropertyRange"
    property: Annotated[
        IRI,
        EntityKind(EntityType.DATA_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]
    range: Annotated[DataRange, EntityPosition(Position.RANGE)]

    @override
    def __str__(self) -> str:
        from ontoloom.ontology.models.literals import _fmt_data_range

        return f"DataPropertyRange({self.property}, {_fmt_data_range(self.range)})"


class FunctionalDataProperty(BaseAxiom):
    """dp has at most one value per individual.

    FunctionalDataProperty(hasAge) -> each thing has at most one age
    """

    type: Literal["FunctionalDataProperty"] = "FunctionalDataProperty"
    property: Annotated[
        IRI,
        EntityKind(EntityType.DATA_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]

    @override
    def __str__(self) -> str:
        return f"FunctionalDataProperty({self.property})"


class HasKey(BaseAxiom):
    """Instances of CE are uniquely identified by the listed properties.

    HasKey(Person, [hasSSN]) -> SSN uniquely identifies a person
    """

    type: Literal["HasKey"] = "HasKey"
    class_expression: Annotated[ClassExpression, EntityPosition(Position.CLASS)]
    object_properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityKind(EntityType.OBJECT_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]
    data_properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityKind(EntityType.DATA_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]

    @model_validator(mode="after")
    def _check_has_properties(self):
        if not self.object_properties and not self.data_properties:
            msg = "HasKey must have at least one object or data property"
            raise ValueError(msg)
        return self

    @override
    def __str__(self) -> str:
        obj = ", ".join(str(p) for p in self.object_properties)
        data = ", ".join(str(p) for p in self.data_properties)
        return f"HasKey({self.class_expression}, [{obj}], [{data}])"


class SubAnnotationPropertyOf(BaseAxiom):
    type: Literal["SubAnnotationPropertyOf"] = "SubAnnotationPropertyOf"
    sub_property: Annotated[
        IRI,
        EntityKind(EntityType.ANNOTATION_PROPERTY),
        EntityPosition(Position.SUB_PROPERTY),
    ]
    super_property: Annotated[
        IRI,
        EntityKind(EntityType.ANNOTATION_PROPERTY),
        EntityPosition(Position.SUPER_PROPERTY),
    ]

    @override
    def __str__(self) -> str:
        return f"SubAnnotationPropertyOf({self.sub_property}, {self.super_property})"


class AnnotationPropertyDomain(BaseAxiom):
    """No logical semantics."""

    type: Literal["AnnotationPropertyDomain"] = "AnnotationPropertyDomain"
    property: Annotated[
        IRI,
        EntityKind(EntityType.ANNOTATION_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]
    domain: Annotated[IRI, EntityPosition(Position.DOMAIN)]

    @override
    def __str__(self) -> str:
        return f"AnnotationPropertyDomain({self.property}, {self.domain})"


class AnnotationPropertyRange(BaseAxiom):
    """No logical semantics."""

    type: Literal["AnnotationPropertyRange"] = "AnnotationPropertyRange"
    property: Annotated[
        IRI,
        EntityKind(EntityType.ANNOTATION_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]
    range: Annotated[IRI, EntityPosition(Position.RANGE)]

    @override
    def __str__(self) -> str:
        return f"AnnotationPropertyRange({self.property}, {self.range})"


class DatatypeDefinition(BaseAxiom):
    type: Literal["DatatypeDefinition"] = "DatatypeDefinition"
    datatype: Annotated[
        IRI,
        EntityKind(EntityType.DATATYPE),
        EntityPosition(Position.ENTITY),
    ]
    data_range: Annotated[DataRange, EntityPosition(Position.RANGE)]

    @override
    def __str__(self) -> str:
        from ontoloom.ontology.models.literals import _fmt_data_range

        return f"DatatypeDefinition({self.datatype}, {_fmt_data_range(self.data_range)})"


class Declaration(BaseAxiom):
    type: Literal["Declaration"] = "Declaration"
    entity_type: EntityType
    iri: Annotated[IRI, EntityPosition(Position.ENTITY)]

    @override
    def __str__(self) -> str:
        return f"Declaration({self.entity_type}, {self.iri})"


Axiom = Annotated[
    (
        AnnotationAssertion
        | SubClassOf
        | EquivalentClasses
        | DisjointClasses
        | SubObjectPropertyOf
        | SubObjectPropertyOfChain
        | EquivalentObjectProperties
        | TransitiveObjectProperty
        | ReflexiveObjectProperty
        | ObjectPropertyDomain
        | ObjectPropertyRange
        | SubDataPropertyOf
        | EquivalentDataProperties
        | DataPropertyDomain
        | DataPropertyRange
        | FunctionalDataProperty
        | HasKey
        | SubAnnotationPropertyOf
        | AnnotationPropertyDomain
        | AnnotationPropertyRange
        | DatatypeDefinition
        | Declaration
        # ABox — Assertions
        | ClassAssertion
        | ObjectPropertyAssertion
        | NegativeObjectPropertyAssertion
        | DataPropertyAssertion
        | NegativeDataPropertyAssertion
        | SameIndividual
        | DifferentIndividuals
    ),
    Field(discriminator="type"),
]
