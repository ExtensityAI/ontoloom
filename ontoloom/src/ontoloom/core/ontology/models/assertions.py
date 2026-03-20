from typing import Annotated, Literal

from pydantic import Field

from ontoloom.core.ontology.models.base import FrozenModel
from ontoloom.core.ontology.models.expressions import ClassExpression
from ontoloom.core.ontology.models.literals import IRI, TypedLiteral

# =============================================================================
# Base
# =============================================================================


class BaseAssertion(FrozenModel):
    """Base for all ABox assertions."""


# =============================================================================
# Class and property assertions
# =============================================================================


class ClassAssertion(BaseAssertion):
    """a ∈ C — individual a is an instance of C.

    ClassAssertion(Dog, Fido)
    """

    type: Literal["ClassAssertion"] = "ClassAssertion"
    class_expression: ClassExpression
    individual: IRI


class ObjectPropertyAssertion(BaseAssertion):
    """r(a, b) — a is related to b by r.

    ObjectPropertyAssertion(owns, Alice, Fido)
    """

    type: Literal["ObjectPropertyAssertion"] = "ObjectPropertyAssertion"
    property: IRI
    source: IRI
    target: IRI


class NegativeObjectPropertyAssertion(BaseAssertion):
    """¬r(a, b) — a is NOT related to b by r.

    NegativeObjectPropertyAssertion(owns, Alice, Rex)
    """

    type: Literal["NegativeObjectPropertyAssertion"] = "NegativeObjectPropertyAssertion"
    property: IRI
    source: IRI
    target: IRI


class DataPropertyAssertion(BaseAssertion):
    """dp(a, v) — a has value v for dp.

    DataPropertyAssertion(hasAge, Alice, "30"^^xsd:integer)
    """

    type: Literal["DataPropertyAssertion"] = "DataPropertyAssertion"
    property: IRI
    individual: IRI
    value: TypedLiteral


class NegativeDataPropertyAssertion(BaseAssertion):
    """¬dp(a, v) — a does NOT have value v for dp.

    NegativeDataPropertyAssertion(hasAge, Alice, "99"^^xsd:integer)
    """

    type: Literal["NegativeDataPropertyAssertion"] = "NegativeDataPropertyAssertion"
    property: IRI
    individual: IRI
    value: TypedLiteral


# =============================================================================
# Individual identity
# =============================================================================


class SameIndividual(BaseAssertion):
    """a = b — both IRIs denote the same entity."""

    type: Literal["SameIndividual"] = "SameIndividual"
    individuals: tuple[IRI, ...] = Field(..., min_length=2)


class DifferentIndividuals(BaseAssertion):
    """a ≠ b — all listed individuals are pairwise distinct."""

    type: Literal["DifferentIndividuals"] = "DifferentIndividuals"
    individuals: tuple[IRI, ...] = Field(..., min_length=2)


# =============================================================================
# Discriminated union
# =============================================================================

Assertion = Annotated[
    (
        ClassAssertion
        | ObjectPropertyAssertion
        | NegativeObjectPropertyAssertion
        | DataPropertyAssertion
        | NegativeDataPropertyAssertion
        | SameIndividual
        | DifferentIndividuals
    ),
    Field(discriminator="type"),
]
