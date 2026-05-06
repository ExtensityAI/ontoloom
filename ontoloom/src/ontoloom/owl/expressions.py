from __future__ import annotations

from typing import Annotated, Literal, override

from pydantic import Field

from ontoloom.models import FrozenModel, tagged_union_meta
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import (
    DataRange,
    LiteralValue,
)
from ontoloom.owl.markers import EntityType, Position, Unordered


class BaseClassExpression(FrozenModel):
    pass


# -- Named class --


class NamedClass(BaseClassExpression):
    """A named (atomic) class. Wraps a Class entity IRI.

    Also used for owl:Thing and owl:Nothing:
        NamedClass(iri=IRI("owl:Thing"))
        NamedClass(iri=IRI("owl:Nothing"))
    """

    type: Literal["NamedClass"] = "NamedClass"
    iri: Annotated[IRI, EntityType.CLASS]

    @override
    def __str__(self) -> str:
        return str(self.iri)


# -- Object property restrictions --


class ObjectSomeValuesFrom(BaseClassExpression):
    """∃r.C -> things related by r to at least one member of C.

    SubClassOf(Animal, ObjectSomeValuesFrom(hasPart, Heart))
        -> every animal has some heart as a part
    """

    type: Literal["ObjectSomeValuesFrom"] = "ObjectSomeValuesFrom"
    property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.RESTRICTION_PROPERTY,
    ]
    filler: Annotated[ClassExpression, Position.FILLER]

    @override
    def __str__(self) -> str:
        return f"ObjectSomeValuesFrom({self.property}, {self.filler})"


class ObjectIntersectionOf(BaseClassExpression):
    """C ⊓ D -> things in ALL listed classes simultaneously.

    ObjectIntersectionOf([Woman, Parent]) -> female parents
    """

    type: Literal["ObjectIntersectionOf"] = "ObjectIntersectionOf"
    operands: Annotated[
        tuple[ClassExpression, ...],
        Unordered(),
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return f"ObjectIntersectionOf({', '.join(str(o) for o in self.operands)})"


class ObjectOneOf(BaseClassExpression):
    """Nominal: {a} -> class containing exactly one individual.

    EL restriction: only a single individual.
    """

    type: Literal["ObjectOneOf"] = "ObjectOneOf"
    individual: Annotated[IRI, EntityType.NAMED_INDIVIDUAL]

    @override
    def __str__(self) -> str:
        return f"ObjectOneOf({self.individual})"


class ObjectHasValue(BaseClassExpression):
    """∃r.{a} -> things related by r to a specific individual.

    ObjectHasValue(hasCreator, :Alice) -> things created by Alice

    Syntactic sugar for ObjectSomeValuesFrom(r, ObjectOneOf({a})).
    """

    type: Literal["ObjectHasValue"] = "ObjectHasValue"
    property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.RESTRICTION_PROPERTY,
    ]
    individual: Annotated[
        IRI,
        EntityType.NAMED_INDIVIDUAL,
        Position.FILLER,
    ]

    @override
    def __str__(self) -> str:
        return f"ObjectHasValue({self.property}, {self.individual})"


class ObjectHasSelf(BaseClassExpression):
    """∃r.Self -> things related to themselves by r.

    ObjectHasSelf(likes) -> things that like themselves
    """

    type: Literal["ObjectHasSelf"] = "ObjectHasSelf"
    property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.RESTRICTION_PROPERTY,
    ]

    @override
    def __str__(self) -> str:
        return f"ObjectHasSelf({self.property})"


# -- Data property restrictions --


class DataSomeValuesFrom(BaseClassExpression):
    """Things with at least one value for dp in the given range.

    DataSomeValuesFrom(hasAge, xsd:integer)
        -> things that have an integer age
    """

    type: Literal["DataSomeValuesFrom"] = "DataSomeValuesFrom"
    property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.RESTRICTION_PROPERTY,
    ]
    range: DataRange

    @override
    def __str__(self) -> str:
        return f"DataSomeValuesFrom({self.property}, {self.range})"


class DataHasValue(BaseClassExpression):
    """Things whose data property has exactly this value.

    DataHasValue(hasName, TypedLiteral("Alice"))
    """

    type: Literal["DataHasValue"] = "DataHasValue"
    property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.RESTRICTION_PROPERTY,
    ]
    value: LiteralValue

    @override
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
    *tagged_union_meta(),
]

ObjectSomeValuesFrom.model_rebuild()
ObjectIntersectionOf.model_rebuild()
