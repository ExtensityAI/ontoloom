"""Constraint variants, query-class mixins, and field validators — pure outputs, no DB access."""

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, Field, model_validator

from ontoloom.errors import OntoloomError
from ontoloom.hashing import AxiomHash
from ontoloom.models import FrozenModel
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import AxiomTag, EntityType, Position
from ontoloom.prefixes.types import PrefixName
from ontoloom.selections.types import SelectionRef

# Each IRI in a MentionsAll becomes its own EXISTS subquery in the SQL plan.
_MENTIONS_ALL_CAP = 8


class MentionsAllOverflowError(OntoloomError):
    """Merged MentionsAll constraints exceed the per-constraint IRI cap."""

    def __init__(self, count: int, cap: int):
        self.count = count
        self.cap = cap
        super().__init__(
            f"Cannot merge MentionsAll constraints: union has {count} IRIs "
            f"but cap is {cap}. Reduce or split the constraint set."
        )


def _sorted_unique[T: str](v: tuple[T, ...]) -> tuple[T, ...]:
    return tuple(sorted(set(v)))


SortedUnique = AfterValidator(_sorted_unique)


class InIRIs(FrozenModel):
    iris: Annotated[tuple[IRI, ...], Field(min_length=1), SortedUnique]


class WithRoles(FrozenModel):
    roles: Annotated[tuple[EntityType, ...], Field(min_length=1), SortedUnique]


class HasRole(FrozenModel):
    pass


class InNamespaces(FrozenModel):
    namespaces: Annotated[tuple[PrefixName, ...], Field(min_length=1), SortedUnique]


class Declared(FrozenModel):
    state: bool


class Deprecated(FrozenModel):
    state: bool

    @model_validator(mode="after")
    def _only_false_supported(self) -> "Deprecated":
        if self.state:
            msg = "Deprecated(state=True) not implemented; only state=False has SQL support"
            raise NotImplementedError(msg)
        return self


class HasAnyProperty(FrozenModel):
    properties: Annotated[tuple[IRI, ...], Field(min_length=1), SortedUnique]


class MentionedIn(FrozenModel):
    hashes: Annotated[tuple[AxiomHash, ...], Field(min_length=1), SortedUnique]


class InPositions(FrozenModel):
    positions: Annotated[tuple[Position, ...], Field(min_length=1), SortedUnique]


class InSelection(FrozenModel):
    ref: SelectionRef


class AlwaysFalse(FrozenModel):
    pass


type EntityConstraint = (
    InIRIs
    | WithRoles
    | HasRole
    | InNamespaces
    | Declared
    | Deprecated
    | HasAnyProperty
    | MentionedIn
    | InPositions
    | InSelection
    | AlwaysFalse
)


class WithTypes(FrozenModel):
    tags: Annotated[tuple[AxiomTag, ...], Field(min_length=1), SortedUnique]


class MentionsAll(FrozenModel):
    iris: Annotated[
        tuple[IRI, ...], Field(min_length=1, max_length=_MENTIONS_ALL_CAP), SortedUnique
    ]


class MentionsAny(FrozenModel):
    iris: Annotated[tuple[IRI, ...], Field(min_length=1), SortedUnique]


class TextMatchKind(StrEnum):
    EXACT = "exact"
    SUBSTRING = "substring"


class WithAnnotationText(FrozenModel):
    text: Annotated[str, Field(min_length=1)]
    properties: Annotated[tuple[IRI, ...], SortedUnique] = ()
    match_kind: TextMatchKind = TextMatchKind.SUBSTRING


class HasAnyAnnotation(FrozenModel):
    properties: Annotated[tuple[IRI, ...], Field(min_length=1), SortedUnique]


type AxiomConstraint = (
    WithTypes
    | MentionsAll
    | MentionsAny
    | WithAnnotationText
    | HasAnyAnnotation
    | InSelection
    | AlwaysFalse
)


class HasEntityConstraints(FrozenModel):
    constraints: tuple[EntityConstraint, ...]


class HasAxiomConstraints(FrozenModel):
    constraints: tuple[AxiomConstraint, ...]


class HasPagination(FrozenModel):
    limit: int | None = None
    offset: int = 0

    @model_validator(mode="after")
    def _validate_pagination(self) -> "HasPagination":
        if self.offset < 0:
            msg = "offset must be >= 0"
            raise ValueError(msg)

        if self.limit is not None and self.limit < 0:
            msg = "limit must be >= 0 if set"
            raise ValueError(msg)

        if self.offset > 0 and self.limit is None:
            msg = "offset > 0 requires limit to be set"
            raise ValueError(msg)

        return self
