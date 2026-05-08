from typing import Annotated, Literal, override

from pydantic import Field, Tag, model_validator

from ontoloom.models import FrozenModel, make_tag_resolver, tagged_union_meta
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

    equivalent_classes: Annotated[
        tuple[ClassExpression, ...],
        Unordered(),
        Position.MEMBER,
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"EquivalentClasses({', '.join(str(e) for e in self.equivalent_classes)})"


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

    @override
    def __str__(self) -> str:
        return f"DisjointClasses({', '.join(str(e) for e in self.disjoint_classes)})"


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

    @override
    def __str__(self) -> str:
        return f"SubObjectPropertyOf({self.sub_object_property}, {self.super_object_property})"


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

    @override
    def __str__(self) -> str:
        chain = ", ".join(str(p) for p in self.chain)
        return f"SubObjectPropertyOfChain([{chain}], {self.super_property})"


class EquivalentObjectProperties(BaseAxiom):
    """r₁ ≡ r₂ -> properties relate the same pairs of individuals."""

    object_properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.OBJECT_PROPERTY,
        Position.MEMBER,
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"EquivalentObjectProperties({', '.join(str(p) for p in self.object_properties)})"


class TransitiveObjectProperty(BaseAxiom):
    """r(x,y) ∧ r(y,z) -> r(x,z)

    Equivalent to SubObjectPropertyOfChain([r, r], r).
    """

    transitive_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ]

    @override
    def __str__(self) -> str:
        return f"TransitiveObjectProperty({self.transitive_property})"


class ReflexiveObjectProperty(BaseAxiom):
    """r(x,x) for every individual x.

    ReflexiveObjectProperty(partOf) -> everything is part of itself
    """

    reflexive_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.PROPERTY,
    ]

    @override
    def __str__(self) -> str:
        return f"ReflexiveObjectProperty({self.reflexive_property})"


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

    @override
    def __str__(self) -> str:
        return f"ObjectPropertyDomain({self.object_property}, {self.domain})"


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

    @override
    def __str__(self) -> str:
        return f"ObjectPropertyRange({self.object_property}, {self.range})"


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

    @override
    def __str__(self) -> str:
        return f"SubDataPropertyOf({self.sub_data_property}, {self.super_data_property})"


class EquivalentDataProperties(BaseAxiom):
    """dp₁ ≡ dp₂ -> data properties have the same values for all individuals."""

    data_properties: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.DATA_PROPERTY,
        Position.MEMBER,
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"EquivalentDataProperties({', '.join(str(p) for p in self.data_properties)})"


class DataPropertyDomain(BaseAxiom):
    """If x has any value for dp, then x ∈ C."""

    data_property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
    ]
    domain: Annotated[ClassExpression, Position.DOMAIN]

    @override
    def __str__(self) -> str:
        return f"DataPropertyDomain({self.data_property}, {self.domain})"


class DataPropertyRange(BaseAxiom):
    """All values of dp fall within this data range."""

    data_property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
    ]
    range: Annotated[DataRange, Position.RANGE]

    @override
    def __str__(self) -> str:
        return f"DataPropertyRange({self.data_property}, {self.range})"


class FunctionalDataProperty(BaseAxiom):
    """dp has at most one value per individual.

    FunctionalDataProperty(hasAge) -> each thing has at most one age
    """

    functional_property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.PROPERTY,
    ]

    @override
    def __str__(self) -> str:
        return f"FunctionalDataProperty({self.functional_property})"


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

    @override
    def __str__(self) -> str:
        return f"SubAnnotationPropertyOf({self.sub_annotation_property}, {self.super_annotation_property})"


class AnnotationPropertyDomain(BaseAxiom):
    """No logical semantics."""

    annotation_property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.PROPERTY,
    ]
    domain: Annotated[IRI, Position.DOMAIN]

    @override
    def __str__(self) -> str:
        return f"AnnotationPropertyDomain({self.annotation_property}, {self.domain})"


class AnnotationPropertyRange(BaseAxiom):
    """No logical semantics."""

    annotation_property: Annotated[
        IRI,
        EntityType.ANNOTATION_PROPERTY,
        Position.PROPERTY,
    ]
    range: Annotated[IRI, Position.RANGE]

    @override
    def __str__(self) -> str:
        return f"AnnotationPropertyRange({self.annotation_property}, {self.range})"


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

    @override
    def __str__(self) -> str:
        obj = ", ".join(str(p) for p in self.object_properties)
        data = ", ".join(str(p) for p in self.data_properties)
        return f"HasKey({self.class_expression}, [{obj}], [{data}])"


class DatatypeDefinition(BaseAxiom):
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

    class_expression: Annotated[ClassExpression, Position.CLASS]
    individual: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.INDIVIDUAL]

    @override
    def __str__(self) -> str:
        return f"ClassAssertion({self.class_expression}, {self.individual})"


class ObjectPropertyAssertion(BaseAxiom):
    """r(a, b) -> a is related to b by r.

    ObjectPropertyAssertion(owns, Alice, Fido)
    """

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

    property: Annotated[IRI, EntityType.OBJECT_PROPERTY, Position.PROPERTY]
    source: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.SOURCE]
    target: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.TARGET]
    negated: Literal[True] = True

    @override
    def __str__(self) -> str:
        return f"NegativeObjectPropertyAssertion({self.property}, {self.source}, {self.target})"


class DataPropertyAssertion(BaseAxiom):
    """dp(a, v) -> a has value v for dp.

    DataPropertyAssertion(hasAge, Alice, "30"^^xsd:integer)
    """

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

    property: Annotated[IRI, EntityType.DATA_PROPERTY, Position.PROPERTY]
    individual: Annotated[IRI, EntityType.NAMED_INDIVIDUAL, Position.INDIVIDUAL]
    value: LiteralValue
    negated: Literal[True] = True

    @override
    def __str__(self) -> str:
        return f"NegativeDataPropertyAssertion({self.property}, {self.individual}, {self.value})"


class SameIndividual(BaseAxiom):
    """a = b -> both IRIs denote the same entity."""

    same_individuals: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.NAMED_INDIVIDUAL,
        Position.MEMBER,
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"SameIndividual({', '.join(str(i) for i in self.same_individuals)})"


class DifferentIndividuals(BaseAxiom):
    """a ≠ b -> all listed individuals are pairwise distinct."""

    different_individuals: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityType.NAMED_INDIVIDUAL,
        Position.MEMBER,
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"DifferentIndividuals({', '.join(str(i) for i in self.different_individuals)})"


# -- Discriminated union of all axiom types --


_AXIOM_CLASSES = (
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
_get_axiom_tag = make_tag_resolver(_AXIOM_CLASSES, union_name="Axiom")


Axiom = Annotated[
    (
        Annotated[AnnotationAssertion, Tag(AnnotationAssertion.tag())]
        | Annotated[SubClassOf, Tag(SubClassOf.tag())]
        | Annotated[EquivalentClasses, Tag(EquivalentClasses.tag())]
        | Annotated[DisjointClasses, Tag(DisjointClasses.tag())]
        | Annotated[SubObjectPropertyOf, Tag(SubObjectPropertyOf.tag())]
        | Annotated[SubObjectPropertyOfChain, Tag(SubObjectPropertyOfChain.tag())]
        | Annotated[EquivalentObjectProperties, Tag(EquivalentObjectProperties.tag())]
        | Annotated[TransitiveObjectProperty, Tag(TransitiveObjectProperty.tag())]
        | Annotated[ReflexiveObjectProperty, Tag(ReflexiveObjectProperty.tag())]
        | Annotated[ObjectPropertyDomain, Tag(ObjectPropertyDomain.tag())]
        | Annotated[ObjectPropertyRange, Tag(ObjectPropertyRange.tag())]
        | Annotated[SubDataPropertyOf, Tag(SubDataPropertyOf.tag())]
        | Annotated[EquivalentDataProperties, Tag(EquivalentDataProperties.tag())]
        | Annotated[DataPropertyDomain, Tag(DataPropertyDomain.tag())]
        | Annotated[DataPropertyRange, Tag(DataPropertyRange.tag())]
        | Annotated[FunctionalDataProperty, Tag(FunctionalDataProperty.tag())]
        | Annotated[SubAnnotationPropertyOf, Tag(SubAnnotationPropertyOf.tag())]
        | Annotated[AnnotationPropertyDomain, Tag(AnnotationPropertyDomain.tag())]
        | Annotated[AnnotationPropertyRange, Tag(AnnotationPropertyRange.tag())]
        | Annotated[HasKey, Tag(HasKey.tag())]
        | Annotated[DatatypeDefinition, Tag(DatatypeDefinition.tag())]
        | Annotated[Declaration, Tag(Declaration.tag())]
        | Annotated[ClassAssertion, Tag(ClassAssertion.tag())]
        | Annotated[ObjectPropertyAssertion, Tag(ObjectPropertyAssertion.tag())]
        | Annotated[NegativeObjectPropertyAssertion, Tag(NegativeObjectPropertyAssertion.tag())]
        | Annotated[DataPropertyAssertion, Tag(DataPropertyAssertion.tag())]
        | Annotated[NegativeDataPropertyAssertion, Tag(NegativeDataPropertyAssertion.tag())]
        | Annotated[SameIndividual, Tag(SameIndividual.tag())]
        | Annotated[DifferentIndividuals, Tag(DifferentIndividuals.tag())]
    ),
    *tagged_union_meta(_get_axiom_tag),
]
