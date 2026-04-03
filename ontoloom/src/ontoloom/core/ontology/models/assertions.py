from typing import Literal

from pydantic import Field

from ontoloom.core.ontology.models.base import BaseAxiom
from ontoloom.core.ontology.models.expressions import ClassExpression
from ontoloom.core.ontology.models.literals import IRI, LangLiteral, TypedLiteral

# =============================================================================
# Class and property assertions
# =============================================================================


class ClassAssertion(BaseAxiom):
    """a ∈ C — individual a is an instance of C.

    ClassAssertion(Dog, Fido)
    """

    type: Literal["ClassAssertion"] = "ClassAssertion"
    class_expression: ClassExpression
    individual: IRI

    def __str__(self) -> str:
        return f"ClassAssertion({self.class_expression}, {self.individual})"


class ObjectPropertyAssertion(BaseAxiom):
    """r(a, b) — a is related to b by r.

    ObjectPropertyAssertion(owns, Alice, Fido)
    """

    type: Literal["ObjectPropertyAssertion"] = "ObjectPropertyAssertion"
    property: IRI
    source: IRI
    target: IRI

    def __str__(self) -> str:
        return f"ObjectPropertyAssertion({self.property}, {self.source}, {self.target})"


class NegativeObjectPropertyAssertion(BaseAxiom):
    """¬r(a, b) — a is NOT related to b by r.

    NegativeObjectPropertyAssertion(owns, Alice, Rex)
    """

    type: Literal["NegativeObjectPropertyAssertion"] = "NegativeObjectPropertyAssertion"
    property: IRI
    source: IRI
    target: IRI

    def __str__(self) -> str:
        return f"NegativeObjectPropertyAssertion({self.property}, {self.source}, {self.target})"


class DataPropertyAssertion(BaseAxiom):
    """dp(a, v) — a has value v for dp.

    DataPropertyAssertion(hasAge, Alice, "30"^^xsd:integer)
    """

    type: Literal["DataPropertyAssertion"] = "DataPropertyAssertion"
    property: IRI
    individual: IRI
    value: TypedLiteral | LangLiteral

    def __str__(self) -> str:
        return f"DataPropertyAssertion({self.property}, {self.individual}, {self.value})"


class NegativeDataPropertyAssertion(BaseAxiom):
    """¬dp(a, v) — a does NOT have value v for dp.

    NegativeDataPropertyAssertion(hasAge, Alice, "99"^^xsd:integer)
    """

    type: Literal["NegativeDataPropertyAssertion"] = "NegativeDataPropertyAssertion"
    property: IRI
    individual: IRI
    value: TypedLiteral | LangLiteral

    def __str__(self) -> str:
        return f"NegativeDataPropertyAssertion({self.property}, {self.individual}, {self.value})"


# =============================================================================
# Individual identity
# =============================================================================


class SameIndividual(BaseAxiom):
    """a = b — both IRIs denote the same entity."""

    type: Literal["SameIndividual"] = "SameIndividual"
    individuals: tuple[IRI, ...] = Field(..., min_length=2)

    def __str__(self) -> str:
        return f"SameIndividual({', '.join(str(i) for i in self.individuals)})"


class DifferentIndividuals(BaseAxiom):
    """a ≠ b — all listed individuals are pairwise distinct."""

    type: Literal["DifferentIndividuals"] = "DifferentIndividuals"
    individuals: tuple[IRI, ...] = Field(..., min_length=2)

    def __str__(self) -> str:
        return f"DifferentIndividuals({', '.join(str(i) for i in self.individuals)})"
