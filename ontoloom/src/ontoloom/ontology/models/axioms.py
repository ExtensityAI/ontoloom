from typing import Annotated, Literal

from pydantic import Field

from ontoloom.ontology.models.assertions import (
    ClassAssertion,
    DataPropertyAssertion,
    DifferentIndividuals,
    NegativeDataPropertyAssertion,
    NegativeObjectPropertyAssertion,
    ObjectPropertyAssertion,
    SameIndividual,
)
from ontoloom.ontology.models.base import BaseAxiom, EntityType
from ontoloom.ontology.models.expressions import ClassExpression
from ontoloom.ontology.models.literals import IRI, DataRange, LangLiteral, TypedLiteral


class AnnotationAssertion(BaseAxiom):
    """An annotation on an entity. No logical semantics.

    AnnotationAssertion(rdfs:label, :Dog, "Dog"@en)
    """

    type: Literal["AnnotationAssertion"] = "AnnotationAssertion"
    property: IRI
    subject: IRI
    value: IRI | TypedLiteral | LangLiteral

    def __str__(self) -> str:
        return f"AnnotationAssertion({self.property}, {self.subject}, {self.value})"


class SubClassOf(BaseAxiom):
    """C ⊑ D — every instance of sub_class is an instance of super_class.

    SubClassOf(Dog, Animal)
        → every dog is an animal
    SubClassOf(Mammal, ∃hasPart.Lung)
        → every mammal has some lung
    """

    type: Literal["SubClassOf"] = "SubClassOf"
    sub_class: ClassExpression
    super_class: ClassExpression

    def __str__(self) -> str:
        return f"SubClassOf({self.sub_class}, {self.super_class})"


class EquivalentClasses(BaseAxiom):
    """C ≡ D — classes have exactly the same instances.

    Use only for true definitions (necessary AND sufficient).

    EquivalentClasses(Mother, Woman ⊓ Parent)
    """

    type: Literal["EquivalentClasses"] = "EquivalentClasses"
    expressions: tuple[ClassExpression, ...] = Field(..., min_length=2)

    def __str__(self) -> str:
        return f"EquivalentClasses({', '.join(str(e) for e in self.expressions)})"


class DisjointClasses(BaseAxiom):
    """Classes share no instances.

    DisjointClasses(Male, Female) → nothing is both male and female
    """

    type: Literal["DisjointClasses"] = "DisjointClasses"
    expressions: tuple[ClassExpression, ...] = Field(..., min_length=2)

    def __str__(self) -> str:
        return f"DisjointClasses({', '.join(str(e) for e in self.expressions)})"


class SubObjectPropertyOf(BaseAxiom):
    """r ⊑ s — if r(x,y) then s(x,y).

    SubObjectPropertyOf(hasMother, hasParent)
    """

    type: Literal["SubObjectPropertyOf"] = "SubObjectPropertyOf"
    sub_property: IRI
    super_property: IRI

    def __str__(self) -> str:
        return f"SubObjectPropertyOf({self.sub_property}, {self.super_property})"


class SubObjectPropertyOfChain(BaseAxiom):
    """r₁ ∘ r₂ ∘ ... ∘ rₙ ⊑ s — property chain.

    Regularity condition must hold. Stick to length-2 chains.

    SubObjectPropertyOfChain([hasParent, hasBrother], hasUncle)
    SubObjectPropertyOfChain([partOf, partOf], partOf)  — transitivity
    """

    type: Literal["SubObjectPropertyOfChain"] = "SubObjectPropertyOfChain"
    chain: tuple[IRI, ...] = Field(..., min_length=2)
    super_property: IRI

    def __str__(self) -> str:
        chain = ", ".join(str(p) for p in self.chain)
        return f"SubObjectPropertyOfChain([{chain}], {self.super_property})"


class EquivalentObjectProperties(BaseAxiom):
    """r₁ ≡ r₂ — properties relate the same pairs of individuals."""

    type: Literal["EquivalentObjectProperties"] = "EquivalentObjectProperties"
    properties: tuple[IRI, ...] = Field(..., min_length=2)

    def __str__(self) -> str:
        return f"EquivalentObjectProperties({', '.join(str(p) for p in self.properties)})"


class TransitiveObjectProperty(BaseAxiom):
    """r(x,y) ∧ r(y,z) → r(x,z)

    Equivalent to SubObjectPropertyOfChain([r, r], r).
    """

    type: Literal["TransitiveObjectProperty"] = "TransitiveObjectProperty"
    property: IRI

    def __str__(self) -> str:
        return f"TransitiveObjectProperty({self.property})"


class ReflexiveObjectProperty(BaseAxiom):
    """r(x,x) for every individual x.

    ReflexiveObjectProperty(partOf) — everything is part of itself
    """

    type: Literal["ReflexiveObjectProperty"] = "ReflexiveObjectProperty"
    property: IRI

    def __str__(self) -> str:
        return f"ReflexiveObjectProperty({self.property})"


class ObjectPropertyDomain(BaseAxiom):
    """If x is related to anything by r, then x is in C.

    This is an inference rule, not documentation.
    If you assert r(x, y), the reasoner infers x ∈ C.
    """

    type: Literal["ObjectPropertyDomain"] = "ObjectPropertyDomain"
    property: IRI
    domain: ClassExpression

    def __str__(self) -> str:
        return f"ObjectPropertyDomain({self.property}, {self.domain})"


class ObjectPropertyRange(BaseAxiom):
    """If anything is related to y by r, then y ∈ C.

    Same caution as domain — this triggers inferences.
    """

    type: Literal["ObjectPropertyRange"] = "ObjectPropertyRange"
    property: IRI
    range: ClassExpression

    def __str__(self) -> str:
        return f"ObjectPropertyRange({self.property}, {self.range})"


class SubDataPropertyOf(BaseAxiom):
    """dp₁ ⊑ dp₂ — if dp₁(x,v) then dp₂(x,v)."""

    type: Literal["SubDataPropertyOf"] = "SubDataPropertyOf"
    sub_property: IRI
    super_property: IRI

    def __str__(self) -> str:
        return f"SubDataPropertyOf({self.sub_property}, {self.super_property})"


class EquivalentDataProperties(BaseAxiom):
    """dp₁ ≡ dp₂ — data properties have the same values for all individuals."""

    type: Literal["EquivalentDataProperties"] = "EquivalentDataProperties"
    properties: tuple[IRI, ...] = Field(..., min_length=2)

    def __str__(self) -> str:
        return f"EquivalentDataProperties({', '.join(str(p) for p in self.properties)})"


class DataPropertyDomain(BaseAxiom):
    """If x has any value for dp, then x ∈ C."""

    type: Literal["DataPropertyDomain"] = "DataPropertyDomain"
    property: IRI
    domain: ClassExpression

    def __str__(self) -> str:
        return f"DataPropertyDomain({self.property}, {self.domain})"


class DataPropertyRange(BaseAxiom):
    """All values of dp fall within this data range."""

    type: Literal["DataPropertyRange"] = "DataPropertyRange"
    property: IRI
    range: DataRange

    def __str__(self) -> str:
        from ontoloom.ontology.models.literals import _fmt_data_range

        return f"DataPropertyRange({self.property}, {_fmt_data_range(self.range)})"


class FunctionalDataProperty(BaseAxiom):
    """dp has at most one value per individual.

    FunctionalDataProperty(hasAge) → each thing has at most one age
    """

    type: Literal["FunctionalDataProperty"] = "FunctionalDataProperty"
    property: IRI

    def __str__(self) -> str:
        return f"FunctionalDataProperty({self.property})"


class HasKey(BaseAxiom):
    """Instances of CE are uniquely identified by the listed properties.

    HasKey(Person, [hasSSN]) → SSN uniquely identifies a person
    """

    type: Literal["HasKey"] = "HasKey"
    class_expression: ClassExpression
    object_properties: tuple[IRI, ...]
    data_properties: tuple[IRI, ...]

    def __str__(self) -> str:
        obj = ", ".join(str(p) for p in self.object_properties)
        data = ", ".join(str(p) for p in self.data_properties)
        return f"HasKey({self.class_expression}, [{obj}], [{data}])"


class SubAnnotationPropertyOf(BaseAxiom):
    type: Literal["SubAnnotationPropertyOf"] = "SubAnnotationPropertyOf"
    sub_property: IRI
    super_property: IRI

    def __str__(self) -> str:
        return f"SubAnnotationPropertyOf({self.sub_property}, {self.super_property})"


class AnnotationPropertyDomain(BaseAxiom):
    """No logical semantics."""

    type: Literal["AnnotationPropertyDomain"] = "AnnotationPropertyDomain"
    property: IRI
    domain: IRI

    def __str__(self) -> str:
        return f"AnnotationPropertyDomain({self.property}, {self.domain})"


class AnnotationPropertyRange(BaseAxiom):
    """No logical semantics."""

    type: Literal["AnnotationPropertyRange"] = "AnnotationPropertyRange"
    property: IRI
    range: IRI

    def __str__(self) -> str:
        return f"AnnotationPropertyRange({self.property}, {self.range})"


class DatatypeDefinition(BaseAxiom):
    type: Literal["DatatypeDefinition"] = "DatatypeDefinition"
    datatype: IRI
    data_range: DataRange

    def __str__(self) -> str:
        from ontoloom.ontology.models.literals import _fmt_data_range

        return f"DatatypeDefinition({self.datatype}, {_fmt_data_range(self.data_range)})"


class Declaration(BaseAxiom):
    type: Literal["Declaration"] = "Declaration"
    entity_type: EntityType
    iri: IRI

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
