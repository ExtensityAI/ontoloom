from __future__ import annotations

from typing import Annotated, Any, TypeGuard, override

from pydantic import Field

from ontoloom.models import FrozenModel, make_tag_resolver, tagged, tagged_union_meta
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import (
    DataRange,
    LiteralValue,
)
from ontoloom.owl.markers import EntityType, Position, Unordered


class BaseClassExpression(FrozenModel):
    pass


def is_class_expression(x: object) -> TypeGuard[IRI | BaseClassExpression]:
    return isinstance(x, (IRI, BaseClassExpression))


# -- Object property restrictions --


class ObjectSomeValuesFrom(BaseClassExpression):
    """∃r.C -> things related by r to at least one member of C.

    SubClassOf(Animal, ObjectSomeValuesFrom(hasPart, Heart))
        -> every animal has some heart as a part
    """

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

    individual: Annotated[IRI, EntityType.NAMED_INDIVIDUAL]

    @override
    def __str__(self) -> str:
        return f"ObjectOneOf({self.individual})"


class ObjectHasValue(BaseClassExpression):
    """∃r.{a} -> things related by r to a specific individual.

    ObjectHasValue(hasCreator, :Alice) -> things created by Alice

    Syntactic sugar for ObjectSomeValuesFrom(r, ObjectOneOf({a})).
    """

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
    """∃r.Self -> things related to themselves by r."""

    self_property: Annotated[
        IRI,
        EntityType.OBJECT_PROPERTY,
        Position.RESTRICTION_PROPERTY,
    ]

    @override
    def __str__(self) -> str:
        return f"ObjectHasSelf({self.self_property})"


# -- Data property restrictions --


class DataSomeValuesFrom(BaseClassExpression):
    """Things with at least one value for dp in the given range.

    DataSomeValuesFrom(hasAge, xsd:integer)
        -> things that have an integer age
    """

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

    property: Annotated[
        IRI,
        EntityType.DATA_PROPERTY,
        Position.RESTRICTION_PROPERTY,
    ]
    value: LiteralValue

    @override
    def __str__(self) -> str:
        return f"DataHasValue({self.property}, {self.value})"


_resolve_class_expression = make_tag_resolver(
    (
        ObjectSomeValuesFrom,
        ObjectIntersectionOf,
        ObjectOneOf,
        ObjectHasValue,
        ObjectHasSelf,
        DataSomeValuesFrom,
        DataHasValue,
    )
)


def _get_class_expression_tag(v: Any):
    # Bare IRI strings (subclass of str) → "IRI" branch; other inputs delegate.
    return IRI.tag() if isinstance(v, str) else _resolve_class_expression(v)


ClassExpression = Annotated[
    (
        tagged(IRI)
        | tagged(ObjectSomeValuesFrom)
        | tagged(ObjectIntersectionOf)
        | tagged(ObjectOneOf)
        | tagged(ObjectHasValue)
        | tagged(ObjectHasSelf)
        | tagged(DataSomeValuesFrom)
        | tagged(DataHasValue)
    ),
    *tagged_union_meta(_get_class_expression_tag, schema_type=("string", "object")),
    EntityType.CLASS,
]

ObjectSomeValuesFrom.model_rebuild()
ObjectIntersectionOf.model_rebuild()
