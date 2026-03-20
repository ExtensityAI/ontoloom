from __future__ import annotations

from typing import Annotated, Literal

from ontoloom.core.ontology.models.literals import DataRange, LangLiteral, TypedLiteral
from pydantic import BaseModel, Field

from ontoloom_mcp.models.expressions import ClassExpression
from ontoloom_mcp.models.iri import (
    AnnotationPropertyIRI,
    DataPropertyIRI,
    ObjectPropertyIRI,
    StrIRI,
)

# =============================================================================
# Base
# =============================================================================


class BaseAxiom(BaseModel):
    """Base for all MCP axiom input models (StrIRI variant)."""


# =============================================================================
# Annotations
# =============================================================================


class AnnotationAssertion(BaseAxiom):
    """An annotation on an entity. No logical semantics.

    AnnotationAssertion(rdfs:label, :Dog, "Dog"@en)
    """

    type: Literal["AnnotationAssertion"] = "AnnotationAssertion"
    property: AnnotationPropertyIRI
    subject: StrIRI
    value: str | TypedLiteral | LangLiteral


# =============================================================================
# TBox — Class axioms
# =============================================================================


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


class EquivalentClasses(BaseAxiom):
    """C ≡ D — classes have exactly the same instances.

    Use only for true definitions (necessary AND sufficient).

    EquivalentClasses(Mother, Woman ⊓ Parent)
    """

    type: Literal["EquivalentClasses"] = "EquivalentClasses"
    expressions: list[ClassExpression] = Field(..., min_length=2)


class DisjointClasses(BaseAxiom):
    """Classes share no instances.

    DisjointClasses(Male, Female) → nothing is both male and female
    """

    type: Literal["DisjointClasses"] = "DisjointClasses"
    expressions: list[ClassExpression] = Field(..., min_length=2)


# =============================================================================
# RBox — Object property axioms
# =============================================================================


class SubObjectPropertyOf(BaseAxiom):
    """r ⊑ s — if r(x,y) then s(x,y).

    SubObjectPropertyOf(hasMother, hasParent)
    """

    type: Literal["SubObjectPropertyOf"] = "SubObjectPropertyOf"
    sub_property: ObjectPropertyIRI
    super_property: ObjectPropertyIRI


class SubObjectPropertyOfChain(BaseAxiom):
    """r₁ ∘ r₂ ∘ ... ∘ rₙ ⊑ s — property chain.

    Regularity condition must hold. Stick to length-2 chains.

    SubObjectPropertyOfChain([hasParent, hasBrother], hasUncle)
    SubObjectPropertyOfChain([partOf, partOf], partOf)  — transitivity
    """

    type: Literal["SubObjectPropertyOfChain"] = "SubObjectPropertyOfChain"
    chain: list[ObjectPropertyIRI] = Field(..., min_length=2)
    super_property: ObjectPropertyIRI


class EquivalentObjectProperties(BaseAxiom):
    """r₁ ≡ r₂ — properties relate the same pairs of individuals."""

    type: Literal["EquivalentObjectProperties"] = "EquivalentObjectProperties"
    properties: list[ObjectPropertyIRI] = Field(..., min_length=2)


class TransitiveObjectProperty(BaseAxiom):
    """r(x,y) ∧ r(y,z) → r(x,z)

    Equivalent to SubObjectPropertyOfChain([r, r], r).
    """

    type: Literal["TransitiveObjectProperty"] = "TransitiveObjectProperty"
    property: ObjectPropertyIRI


class ReflexiveObjectProperty(BaseAxiom):
    """r(x,x) for every individual x.

    ReflexiveObjectProperty(partOf) — everything is part of itself
    """

    type: Literal["ReflexiveObjectProperty"] = "ReflexiveObjectProperty"
    property: ObjectPropertyIRI


class ObjectPropertyDomain(BaseAxiom):
    """If x is related to anything by r, then x is in C.

    This is an inference rule, not documentation.
    If you assert r(x, y), the reasoner infers x ∈ C.
    """

    type: Literal["ObjectPropertyDomain"] = "ObjectPropertyDomain"
    property: ObjectPropertyIRI
    domain: ClassExpression


class ObjectPropertyRange(BaseAxiom):
    """If anything is related to y by r, then y ∈ C.

    Same caution as domain — this triggers inferences.
    """

    type: Literal["ObjectPropertyRange"] = "ObjectPropertyRange"
    property: ObjectPropertyIRI
    range: ClassExpression


# =============================================================================
# RBox — Data property axioms
# =============================================================================


class SubDataPropertyOf(BaseAxiom):
    """dp₁ ⊑ dp₂ — if dp₁(x,v) then dp₂(x,v)."""

    type: Literal["SubDataPropertyOf"] = "SubDataPropertyOf"
    sub_property: DataPropertyIRI
    super_property: DataPropertyIRI


class EquivalentDataProperties(BaseAxiom):
    """dp₁ ≡ dp₂ — data properties have the same values for all individuals."""

    type: Literal["EquivalentDataProperties"] = "EquivalentDataProperties"
    properties: list[DataPropertyIRI] = Field(..., min_length=2)


class DataPropertyDomain(BaseAxiom):
    """If x has any value for dp, then x ∈ C."""

    type: Literal["DataPropertyDomain"] = "DataPropertyDomain"
    property: DataPropertyIRI
    domain: ClassExpression


class DataPropertyRange(BaseAxiom):
    """All values of dp fall within this data range."""

    type: Literal["DataPropertyRange"] = "DataPropertyRange"
    property: DataPropertyIRI
    range: DataRange


class FunctionalDataProperty(BaseAxiom):
    """dp has at most one value per individual.

    FunctionalDataProperty(hasAge) → each thing has at most one age
    """

    type: Literal["FunctionalDataProperty"] = "FunctionalDataProperty"
    property: DataPropertyIRI


# =============================================================================
# HasKey
# =============================================================================


class HasKey(BaseAxiom):
    """Instances of CE are uniquely identified by the listed properties.

    HasKey(Person, [hasSSN]) → SSN uniquely identifies a person
    """

    type: Literal["HasKey"] = "HasKey"
    class_expression: ClassExpression
    object_properties: list[ObjectPropertyIRI]
    data_properties: list[DataPropertyIRI]


# =============================================================================
# Discriminated union
# =============================================================================

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
    ),
    Field(discriminator="type"),
]
