"""Constraint variants, query-class mixins, and field validators — pure outputs, no DB access."""

from typing import Annotated

from pydantic import AfterValidator, Field, model_validator

from ontoloom.axioms.hashing import AxiomHash
from ontoloom.models import FrozenModel
from ontoloom.owl.axioms import AxiomTag
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType, Position
from ontoloom.owl.prefix_name import PrefixName
from ontoloom.selections.types import SelectionName

# Each IRI in a MentionsAll becomes its own EXISTS subquery in the SQL plan.
_MENTIONS_ALL_CAP = 8


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


class EntityTextMatches(FrozenModel):
    query: str
    properties: tuple[IRI, ...] = ()


class InAxiomSelection(FrozenModel):
    name: SelectionName


class InEntitySelection(FrozenModel):
    name: SelectionName


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
    | EntityTextMatches
    | InAxiomSelection
    | InEntitySelection
)


class WithTypes(FrozenModel):
    tags: Annotated[tuple[AxiomTag, ...], Field(min_length=1), SortedUnique]


class MentionsAll(FrozenModel):
    iris: Annotated[
        tuple[IRI, ...], Field(min_length=1, max_length=_MENTIONS_ALL_CAP), SortedUnique
    ]


class MentionsAny(FrozenModel):
    iris: Annotated[tuple[IRI, ...], Field(min_length=1), SortedUnique]


class HasAnyAnnotation(FrozenModel):
    properties: Annotated[tuple[IRI, ...], Field(min_length=1), SortedUnique]


class AnnotationTextMatches(FrozenModel):
    query: str
    properties: tuple[IRI, ...] = ()


type AxiomConstraint = (
    WithTypes
    | MentionsAll
    | MentionsAny
    | HasAnyAnnotation
    | AnnotationTextMatches
    | InAxiomSelection
    | InEntitySelection
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
