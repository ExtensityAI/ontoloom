from typing import Annotated, Literal, override

from pydantic import Field

from ontoloom.ontology.models.base import BaseAxiom
from ontoloom.ontology.models.expressions import ClassExpression
from ontoloom.ontology.models.literals import IRI, EntityType, LangLiteral, Position, TypedLiteral
from ontoloom.ontology.models.markers import EntityKind, EntityPosition, Unordered


class ClassAssertion(BaseAxiom):
    """a ∈ C — individual a is an instance of C.

    ClassAssertion(Dog, Fido)
    """

    type: Literal["ClassAssertion"] = "ClassAssertion"
    class_expression: Annotated[ClassExpression, EntityPosition(Position.CLASS)]
    individual: Annotated[
        IRI, EntityKind(EntityType.NAMED_INDIVIDUAL), EntityPosition(Position.INDIVIDUAL)
    ]

    @override
    def __str__(self) -> str:
        return f"ClassAssertion({self.class_expression}, {self.individual})"


class ObjectPropertyAssertion(BaseAxiom):
    """r(a, b) — a is related to b by r.

    ObjectPropertyAssertion(owns, Alice, Fido)
    """

    type: Literal["ObjectPropertyAssertion"] = "ObjectPropertyAssertion"
    property: Annotated[
        IRI, EntityKind(EntityType.OBJECT_PROPERTY), EntityPosition(Position.PROPERTY)
    ]
    source: Annotated[IRI, EntityKind(EntityType.NAMED_INDIVIDUAL), EntityPosition(Position.SOURCE)]
    target: Annotated[IRI, EntityKind(EntityType.NAMED_INDIVIDUAL), EntityPosition(Position.TARGET)]

    @override
    def __str__(self) -> str:
        return f"ObjectPropertyAssertion({self.property}, {self.source}, {self.target})"


class NegativeObjectPropertyAssertion(BaseAxiom):
    """¬r(a, b) — a is NOT related to b by r.

    NegativeObjectPropertyAssertion(owns, Alice, Rex)
    """

    type: Literal["NegativeObjectPropertyAssertion"] = "NegativeObjectPropertyAssertion"
    property: Annotated[
        IRI, EntityKind(EntityType.OBJECT_PROPERTY), EntityPosition(Position.PROPERTY)
    ]
    source: Annotated[IRI, EntityKind(EntityType.NAMED_INDIVIDUAL), EntityPosition(Position.SOURCE)]
    target: Annotated[IRI, EntityKind(EntityType.NAMED_INDIVIDUAL), EntityPosition(Position.TARGET)]

    @override
    def __str__(self) -> str:
        return f"NegativeObjectPropertyAssertion({self.property}, {self.source}, {self.target})"


class DataPropertyAssertion(BaseAxiom):
    """dp(a, v) — a has value v for dp.

    DataPropertyAssertion(hasAge, Alice, "30"^^xsd:integer)
    """

    type: Literal["DataPropertyAssertion"] = "DataPropertyAssertion"
    property: Annotated[
        IRI, EntityKind(EntityType.DATA_PROPERTY), EntityPosition(Position.PROPERTY)
    ]
    individual: Annotated[
        IRI, EntityKind(EntityType.NAMED_INDIVIDUAL), EntityPosition(Position.INDIVIDUAL)
    ]
    value: TypedLiteral | LangLiteral

    @override
    def __str__(self) -> str:
        return f"DataPropertyAssertion({self.property}, {self.individual}, {self.value})"


class NegativeDataPropertyAssertion(BaseAxiom):
    """¬dp(a, v) — a does NOT have value v for dp.

    NegativeDataPropertyAssertion(hasAge, Alice, "99"^^xsd:integer)
    """

    type: Literal["NegativeDataPropertyAssertion"] = "NegativeDataPropertyAssertion"
    property: Annotated[
        IRI, EntityKind(EntityType.DATA_PROPERTY), EntityPosition(Position.PROPERTY)
    ]
    individual: Annotated[
        IRI, EntityKind(EntityType.NAMED_INDIVIDUAL), EntityPosition(Position.INDIVIDUAL)
    ]
    value: TypedLiteral | LangLiteral

    @override
    def __str__(self) -> str:
        return f"NegativeDataPropertyAssertion({self.property}, {self.individual}, {self.value})"


class SameIndividual(BaseAxiom):
    """a = b — both IRIs denote the same entity."""

    type: Literal["SameIndividual"] = "SameIndividual"
    individuals: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityKind(EntityType.NAMED_INDIVIDUAL),
        EntityPosition(Position.MEMBER),
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"SameIndividual({', '.join(str(i) for i in self.individuals)})"


class DifferentIndividuals(BaseAxiom):
    """a ≠ b — all listed individuals are pairwise distinct."""

    type: Literal["DifferentIndividuals"] = "DifferentIndividuals"
    individuals: Annotated[
        tuple[IRI, ...],
        Unordered(),
        EntityKind(EntityType.NAMED_INDIVIDUAL),
        EntityPosition(Position.MEMBER),
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"DifferentIndividuals({', '.join(str(i) for i in self.individuals)})"
