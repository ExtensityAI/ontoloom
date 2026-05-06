from typing import Annotated, Literal, override

from pydantic import Field, model_validator

from ontoloom.models import FrozenModel, tagged_union_meta
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


# -- Annotation axioms --


class AnnotationAssertion(BaseAxiom):
    """An annotation on an entity. No logical semantics.

    AnnotationAssertion(rdfs:label, :Dog, "Dog"@en)
    """

    type: Literal["AnnotationAssertion"] = "AnnotationAssertion"
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

    @override
    def __str__(self) -> str:
        return f"AnnotationAssertion({self.property}, {self.subject}, {self.value})"


# -- TBox: class axioms --


class SubClassOf(BaseAxiom):
    """C ⊑ D -> every instance of sub_class is an instance of super_class.

    SubClassOf(Dog, Animal)
        -> every dog is an animal
    SubClassOf(Mammal, ∃hasPart.Lung)
        -> every mammal has some lung
    """

    type: Literal["SubClassOf"] = "SubClassOf"
    sub_class: Annotated[ClassExpression, Position.SUB_CLASS]
    super_class: Annotated[ClassExpression, Position.SUPER_CLASS]

    @override
    def __str__(self) -> str:
        return f"SubClassOf({self.sub_class}, {self.super_class})"


class EquivalentClasses(BaseAxiom):
    """C ≡ D -> classes have exactly the same instances.

    Use only for true definitions (necessary AND sufficient).

    EquivalentClasses(Mother, Woman ⊓ Parent)
    """

    type: Literal["EquivalentClasses"] = "EquivalentClasses"
    expressions: Annotated[
        tuple[ClassExpression, ...],
        Unordered(),
        Position.MEMBER,
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
        Position.MEMBER,
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"DisjointClasses({', '.join(str(e) for e in self.expressions)})"


# -- RBox: object property axioms --


class SubObjectPropertyOf(BaseAxiom):
    """r ⊑ s -> if r(x,y) then s(x,y).

    SubObjectPropertyOf(hasMother, hasParent)
    """

    type: Literal["SubObjectPropertyOf"] = "SubObjectPropertyOf"
    sub_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.SUB_PROPERTY,
    ]
    super_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.SUPER_PROPERTY,
    ]

    @override
    def __str__(self) -> str:
        return f"SubObjectPropertyOf({self.sub_property}, {self.super_property})"


class SubObjectPropertyOfChain(BaseAxiom):
    """r₁ ∘ r₂ ∘ ... ∘ rₙ ⊑ s -> property chain.

    Regularity condition must hold. Stick to length-2 chains.

    SubObjectPropertyOfChain([hasParent, hasBrother], hasUncle)
    SubObjectPropertyOfChain([partOf, partOf], partOf)  -> transitivity
    """

    type: Literal["SubObjectPropertyOfChain"] = "SubObjectPropertyOfChain"
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

    @override
    def __str__(self) -> str:
        chain = ", ".join(str(p) for p in self.chain)
        return f"SubObjectPropertyOfChain([{chain}], {self.super_property})"


class EquivalentObjectProperties(BaseAxiom):
    """r₁ ≡ r₂ -> properties relate the same pairs of individuals."""

    type: Literal["EquivalentObjectProperties"] = "EquivalentObjectProperties"
    properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.OBJECT_PROPERTY,
        Position.MEMBER,
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
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ]

    @override
    def __str__(self) -> str:
        return f"TransitiveObjectProperty({self.property})"


class ReflexiveObjectProperty(BaseAxiom):
    """r(x,x) for every individual x.

    ReflexiveObjectProperty(partOf) -> everything is part of itself
    """

    type: Literal["ReflexiveObjectProperty"] = "ReflexiveObjectProperty"
    property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
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
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ]
    domain: Annotated[ClassExpression, Position.DOMAIN]

    @override
    def __str__(self) -> str:
        return f"ObjectPropertyDomain({self.property}, {self.domain})"


class ObjectPropertyRange(BaseAxiom):
    """If anything is related to y by r, then y ∈ C.

    Same caution as domain -> this triggers inferences.
    """

    type: Literal["ObjectPropertyRange"] = "ObjectPropertyRange"
    property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ]
    range: Annotated[ClassExpression, Position.RANGE]

    @override
    def __str__(self) -> str:
        return f"ObjectPropertyRange({self.property}, {self.range})"


# -- RBox: data property axioms --


class SubDataPropertyOf(BaseAxiom):
    """dp₁ ⊑ dp₂ -> if dp₁(x,v) then dp₂(x,v)."""

    type: Literal["SubDataPropertyOf"] = "SubDataPropertyOf"
    sub_property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.SUB_PROPERTY,
    ]
    super_property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.SUPER_PROPERTY,
    ]

    @override
    def __str__(self) -> str:
        return f"SubDataPropertyOf({self.sub_property}, {self.super_property})"


class EquivalentDataProperties(BaseAxiom):
    """dp₁ ≡ dp₂ -> data properties have the same values for all individuals."""

    type: Literal["EquivalentDataProperties"] = "EquivalentDataProperties"
    properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.DATA_PROPERTY,
        Position.MEMBER,
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
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
    ]
    domain: Annotated[ClassExpression, Position.DOMAIN]

    @override
    def __str__(self) -> str:
        return f"DataPropertyDomain({self.property}, {self.domain})"


class DataPropertyRange(BaseAxiom):
    """All values of dp fall within this data range."""

    type: Literal["DataPropertyRange"] = "DataPropertyRange"
    property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
    ]
    range: Annotated[DataRange, Position.RANGE]

    @override
    def __str__(self) -> str:
        return f"DataPropertyRange({self.property}, {self.range})"


class FunctionalDataProperty(BaseAxiom):
    """dp has at most one value per individual.

    FunctionalDataProperty(hasAge) -> each thing has at most one age
    """

    type: Literal["FunctionalDataProperty"] = "FunctionalDataProperty"
    property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
    ]

    @override
    def __str__(self) -> str:
        return f"FunctionalDataProperty({self.property})"


# -- Annotation property axioms --


class SubAnnotationPropertyOf(BaseAxiom):
    type: Literal["SubAnnotationPropertyOf"] = "SubAnnotationPropertyOf"
    sub_property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.SUB_PROPERTY,
    ]
    super_property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.SUPER_PROPERTY,
    ]

    @override
    def __str__(self) -> str:
        return f"SubAnnotationPropertyOf({self.sub_property}, {self.super_property})"


class AnnotationPropertyDomain(BaseAxiom):
    """No logical semantics."""

    type: Literal["AnnotationPropertyDomain"] = "AnnotationPropertyDomain"
    property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.PROPERTY,
    ]
    domain: Annotated[IRI, Position.DOMAIN]

    @override
    def __str__(self) -> str:
        return f"AnnotationPropertyDomain({self.property}, {self.domain})"


class AnnotationPropertyRange(BaseAxiom):
    """No logical semantics."""

    type: Literal["AnnotationPropertyRange"] = "AnnotationPropertyRange"
    property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.PROPERTY,
    ]
    range: Annotated[IRI, Position.RANGE]

    @override
    def __str__(self) -> str:
        return f"AnnotationPropertyRange({self.property}, {self.range})"


# -- Schema axioms --


class HasKey(BaseAxiom):
    """Instances of CE are uniquely identified by the listed properties.

    HasKey(Person, [hasSSN]) -> SSN uniquely identifies a person
    """

    type: Literal["HasKey"] = "HasKey"
    class_expression: Annotated[ClassExpression, Position.CLASS]
    object_properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ]
    data_properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
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


class DatatypeDefinition(BaseAxiom):
    type: Literal["DatatypeDefinition"] = "DatatypeDefinition"
    datatype: Annotated[
        IRI,
        EntityType.DATATYPE,
        Position.ENTITY,
    ]
    data_range: Annotated[DataRange, Position.RANGE]

    @override
    def __str__(self) -> str:
        return f"DatatypeDefinition({self.datatype}, {self.data_range})"


class Declaration(BaseAxiom):
    type: Literal["Declaration"] = "Declaration"
    entity_type: EntityType
    iri: Annotated[IRI, Position.ENTITY]

    @override
    def __str__(self) -> str:
        return f"Declaration({self.entity_type}, {self.iri})"


# -- ABox: assertions --


class ClassAssertion(BaseAxiom):
    """a ∈ C -> individual a is an instance of C.

    ClassAssertion(Dog, Fido)
    """

    type: Literal["ClassAssertion"] = "ClassAssertion"
    class_expression: Annotated[ClassExpression, Position.CLASS]
    individual: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.INDIVIDUAL]

    @override
    def __str__(self) -> str:
        return f"ClassAssertion({self.class_expression}, {self.individual})"


class ObjectPropertyAssertion(BaseAxiom):
    """r(a, b) -> a is related to b by r.

    ObjectPropertyAssertion(owns, Alice, Fido)
    """

    type: Literal["ObjectPropertyAssertion"] = "ObjectPropertyAssertion"
    property: Annotated[IRI, EntityType.OBJECT_PROPERTY, Position.PROPERTY]
    source: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.SOURCE]
    target: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.TARGET]

    @override
    def __str__(self) -> str:
        return f"ObjectPropertyAssertion({self.property}, {self.source}, {self.target})"


class NegativeObjectPropertyAssertion(BaseAxiom):
    """¬r(a, b) -> a is NOT related to b by r.

    NegativeObjectPropertyAssertion(owns, Alice, Rex)
    """

    type: Literal["NegativeObjectPropertyAssertion"] = "NegativeObjectPropertyAssertion"
    property: Annotated[IRI, EntityType.OBJECT_PROPERTY, Position.PROPERTY]
    source: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.SOURCE]
    target: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.TARGET]

    @override
    def __str__(self) -> str:
        return f"NegativeObjectPropertyAssertion({self.property}, {self.source}, {self.target})"


class DataPropertyAssertion(BaseAxiom):
    """dp(a, v) -> a has value v for dp.

    DataPropertyAssertion(hasAge, Alice, "30"^^xsd:integer)
    """

    type: Literal["DataPropertyAssertion"] = "DataPropertyAssertion"
    property: Annotated[IRI, EntityType.DATA_PROPERTY, Position.PROPERTY]
    individual: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.INDIVIDUAL]
    value: LiteralValue

    @override
    def __str__(self) -> str:
        return f"DataPropertyAssertion({self.property}, {self.individual}, {self.value})"


class NegativeDataPropertyAssertion(BaseAxiom):
    """¬dp(a, v) -> a does NOT have value v for dp.

    NegativeDataPropertyAssertion(hasAge, Alice, "99"^^xsd:integer)
    """

    type: Literal["NegativeDataPropertyAssertion"] = "NegativeDataPropertyAssertion"
    property: Annotated[IRI, EntityType.DATA_PROPERTY, Position.PROPERTY]
    individual: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.INDIVIDUAL]
    value: LiteralValue

    @override
    def __str__(self) -> str:
        return f"NegativeDataPropertyAssertion({self.property}, {self.individual}, {self.value})"


class SameIndividual(BaseAxiom):
    """a = b -> both IRIs denote the same entity."""

    type: Literal["SameIndividual"] = "SameIndividual"
    individuals: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.NAMED_INDIVIDUAL,
        Position.MEMBER,
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"SameIndividual({', '.join(str(i) for i in self.individuals)})"


class DifferentIndividuals(BaseAxiom):
    """a ≠ b -> all listed individuals are pairwise distinct."""

    type: Literal["DifferentIndividuals"] = "DifferentIndividuals"
    individuals: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.NAMED_INDIVIDUAL,
        Position.MEMBER,
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"DifferentIndividuals({', '.join(str(i) for i in self.individuals)})"


# -- Discriminated union of all axiom types --


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
        | SubAnnotationPropertyOf
        | AnnotationPropertyDomain
        | AnnotationPropertyRange
        | HasKey
        | DatatypeDefinition
        | Declaration
        | ClassAssertion
        | ObjectPropertyAssertion
        | NegativeObjectPropertyAssertion
        | DataPropertyAssertion
        | NegativeDataPropertyAssertion
        | SameIndividual
        | DifferentIndividuals
    ),
    *tagged_union_meta(),
]
