from __future__ import annotations

from typing import Literal

from ontoloom.core.ontology.models.literals import DataRange, TypedLiteral
from pydantic import BaseModel, Field

from ontoloom_mcp.models.iri import (
    ClassIRI,
    DataPropertyIRI,
    IndividualIRI,
    ObjectPropertyIRI,
)


class BaseClassExpression(BaseModel):
    """Base for all MCP class expressions (StrIRI variant)."""


# -- Named class --


class NamedClass(BaseClassExpression):
    """A named (atomic) class.

    NamedClass(iri=":Dog")
    NamedClass(iri="owl:Thing")
    """

    type: Literal["NamedClass"] = "NamedClass"
    iri: ClassIRI


# -- Object property restrictions --


class ObjectSomeValuesFrom(BaseClassExpression):
    """∃r.C — things related by r to at least one member of C.

    SubClassOf(Animal, ObjectSomeValuesFrom(hasPart, Heart))
        → every animal has some heart as a part
    """

    type: Literal["ObjectSomeValuesFrom"] = "ObjectSomeValuesFrom"
    property: ObjectPropertyIRI
    filler: ClassExpression


class ObjectIntersectionOf(BaseClassExpression):
    """C ⊓ D — things in ALL listed classes simultaneously.

    ObjectIntersectionOf([Woman, Parent]) → female parents
    """

    type: Literal["ObjectIntersectionOf"] = "ObjectIntersectionOf"
    operands: list[ClassExpression] = Field(..., min_length=2)


class ObjectOneOf(BaseClassExpression):
    """Nominal: {a} — class containing exactly one individual.

    EL restriction: only a single individual.
    """

    type: Literal["ObjectOneOf"] = "ObjectOneOf"
    individual: IndividualIRI


class ObjectHasValue(BaseClassExpression):
    """∃r.{a} — things related by r to a specific individual.

    ObjectHasValue(hasCreator, :Alice) → things created by Alice

    Syntactic sugar for ObjectSomeValuesFrom(r, ObjectOneOf({a})).
    """

    type: Literal["ObjectHasValue"] = "ObjectHasValue"
    property: ObjectPropertyIRI
    individual: IndividualIRI


class ObjectHasSelf(BaseClassExpression):
    """∃r.Self — things related to themselves by r.

    ObjectHasSelf(likes) → things that like themselves
    """

    type: Literal["ObjectHasSelf"] = "ObjectHasSelf"
    property: ObjectPropertyIRI


# -- Data property restrictions --


class DataSomeValuesFrom(BaseClassExpression):
    """Things with at least one value for dp in the given range.

    DataSomeValuesFrom(hasAge, xsd:integer)
        → things that have an integer age
    """

    type: Literal["DataSomeValuesFrom"] = "DataSomeValuesFrom"
    property: DataPropertyIRI
    range: DataRange


class DataHasValue(BaseClassExpression):
    """Things whose data property has exactly this value.

    DataHasValue(hasName, TypedLiteral("Alice"))
    """

    type: Literal["DataHasValue"] = "DataHasValue"
    property: DataPropertyIRI
    value: TypedLiteral


ClassExpression = (
    ClassIRI
    | NamedClass
    | ObjectSomeValuesFrom
    | ObjectIntersectionOf
    | ObjectOneOf
    | ObjectHasValue
    | ObjectHasSelf
    | DataSomeValuesFrom
    | DataHasValue
)

ObjectSomeValuesFrom.model_rebuild()
ObjectIntersectionOf.model_rebuild()
