from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from ontoloom.core.ontology.models.base import FrozenModel
from ontoloom.core.ontology.models.literals import IRI, DataRange, TypedLiteral


class _BaseClassExpression(FrozenModel):
    """Base for all OWL 2 EL class expressions."""


# -- Named class --


class NamedClass(_BaseClassExpression):
    """A named (atomic) class. Wraps a Class entity IRI.

    Also used for owl:Thing and owl:Nothing:
        NamedClass(iri=IRI(prefix="owl", local_name="Thing"))
        NamedClass(iri=IRI(prefix="owl", local_name="Nothing"))
    """

    type: Literal["NamedClass"] = "NamedClass"
    iri: IRI

    def __str__(self) -> str:
        return str(self.iri)


# -- Object property restrictions --


class ObjectSomeValuesFrom(_BaseClassExpression):
    """∃r.C — things related by r to at least one member of C.

    SubClassOf(Animal, ObjectSomeValuesFrom(hasPart, Heart))
        → every animal has some heart as a part
    """

    type: Literal["ObjectSomeValuesFrom"] = "ObjectSomeValuesFrom"
    property: IRI
    filler: ClassExpression

    def __str__(self) -> str:
        return f"ObjectSomeValuesFrom({self.property}, {self.filler})"


class ObjectIntersectionOf(_BaseClassExpression):
    """C ⊓ D — things in ALL listed classes simultaneously.

    ObjectIntersectionOf([Woman, Parent]) → female parents
    """

    type: Literal["ObjectIntersectionOf"] = "ObjectIntersectionOf"
    operands: tuple[ClassExpression, ...] = Field(..., min_length=2)

    def __str__(self) -> str:
        return f"ObjectIntersectionOf({', '.join(str(o) for o in self.operands)})"


class ObjectOneOf(_BaseClassExpression):
    """Nominal: {a} — class containing exactly one individual.

    EL restriction: only a single individual.
    """

    type: Literal["ObjectOneOf"] = "ObjectOneOf"
    individual: IRI

    def __str__(self) -> str:
        return f"ObjectOneOf({self.individual})"


class ObjectHasValue(_BaseClassExpression):
    """∃r.{a} — things related by r to a specific individual.

    ObjectHasValue(hasCreator, :Alice) → things created by Alice

    Syntactic sugar for ObjectSomeValuesFrom(r, ObjectOneOf({a})).
    """

    type: Literal["ObjectHasValue"] = "ObjectHasValue"
    property: IRI
    individual: IRI

    def __str__(self) -> str:
        return f"ObjectHasValue({self.property}, {self.individual})"


class ObjectHasSelf(_BaseClassExpression):
    """∃r.Self — things related to themselves by r.

    ObjectHasSelf(likes) → things that like themselves
    """

    type: Literal["ObjectHasSelf"] = "ObjectHasSelf"
    property: IRI

    def __str__(self) -> str:
        return f"ObjectHasSelf({self.property})"


# -- Data property restrictions --


class DataSomeValuesFrom(_BaseClassExpression):
    """Things with at least one value for dp in the given range.

    DataSomeValuesFrom(hasAge, xsd:integer)
        → things that have an integer age
    """

    type: Literal["DataSomeValuesFrom"] = "DataSomeValuesFrom"
    property: IRI
    range: DataRange

    def __str__(self) -> str:
        from ontoloom.core.ontology.models.literals import _fmt_data_range

        return f"DataSomeValuesFrom({self.property}, {_fmt_data_range(self.range)})"


class DataHasValue(_BaseClassExpression):
    """Things whose data property has exactly this value.

    DataHasValue(hasName, TypedLiteral("Alice"))
    """

    type: Literal["DataHasValue"] = "DataHasValue"
    property: IRI
    value: TypedLiteral

    def __str__(self) -> str:
        return f"DataHasValue({self.property}, {self.value})"


ClassExpression = Annotated[
    (
        NamedClass
        | ObjectSomeValuesFrom
        | ObjectIntersectionOf
        | ObjectOneOf
        | ObjectHasValue
        | ObjectHasSelf
        | DataSomeValuesFrom
        | DataHasValue
    ),
    Field(discriminator="type"),
]

ObjectSomeValuesFrom.model_rebuild()
ObjectIntersectionOf.model_rebuild()
