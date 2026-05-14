"""Constraint variants and field validators — pure outputs, no DB access."""

from pydantic import Field, field_validator, model_validator

from ontoloom.hashing import AxiomHash
from ontoloom.models import FrozenModel
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType, Position
from ontoloom.prefixes.types import PrefixName
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.selections.types import SelectionKind, SelectionKindError, SelectionName


class WithIRIs(FrozenModel):
    iris: tuple[IRI, ...] = Field(min_length=1)

    @field_validator("iris", mode="after")
    @classmethod
    def _dedupe_sort(cls, v: tuple[IRI, ...]) -> tuple[IRI, ...]:
        return tuple(sorted(set(v)))


class WithRoles(FrozenModel):
    roles: tuple[EntityType, ...] = Field(min_length=1)

    @field_validator("roles", mode="after")
    @classmethod
    def _dedupe_sort(cls, v: tuple[EntityType, ...]) -> tuple[EntityType, ...]:
        return tuple(sorted(set(v)))


class HasEntityRole(FrozenModel):
    pass


class InNamespaces(FrozenModel):
    namespaces: tuple[PrefixName, ...] = Field(min_length=1)

    @field_validator("namespaces", mode="after")
    @classmethod
    def _dedupe_sort(cls, v: tuple[PrefixName, ...]) -> tuple[PrefixName, ...]:
        return tuple(sorted(set(v)))


class Declared(FrozenModel):
    state: bool


class NotDeprecated(FrozenModel):
    pass


class WithAnyProperty(FrozenModel):
    properties: tuple[IRI, ...] = Field(min_length=1)

    @field_validator("properties", mode="after")
    @classmethod
    def _dedupe_sort(cls, v: tuple[IRI, ...]) -> tuple[IRI, ...]:
        return tuple(sorted(set(v)))


class MentionedInAxioms(FrozenModel):
    hashes: tuple[AxiomHash, ...] = Field(min_length=1)

    @field_validator("hashes", mode="after")
    @classmethod
    def _dedupe_sort(cls, v: tuple[AxiomHash, ...]) -> tuple[AxiomHash, ...]:
        return tuple(sorted(set(v)))


class InPositions(FrozenModel):
    positions: tuple[Position, ...] = Field(min_length=1)

    @field_validator("positions", mode="after")
    @classmethod
    def _dedupe_sort(cls, v: tuple[Position, ...]) -> tuple[Position, ...]:
        return tuple(sorted(set(v)))


class InSelection(FrozenModel):
    ref: ResolvedSelection
    expected_kind: SelectionKind | None = None

    @model_validator(mode="after")
    def _check_kind(self) -> "InSelection":
        if self.expected_kind is not None and self.expected_kind != self.ref.kind:
            raise SelectionKindError(
                SelectionName(self.ref.bare_name),
                self.expected_kind,
                self.ref.kind,
                "query scope",
            )

        return self


class AlwaysFalse(FrozenModel):
    pass


type EntityConstraint = (
    WithIRIs
    | WithRoles
    | HasEntityRole
    | InNamespaces
    | Declared
    | NotDeprecated
    | WithAnyProperty
    | MentionedInAxioms
    | InPositions
    | InSelection
    | AlwaysFalse
)


class OfTypes(FrozenModel):
    tags: tuple[str, ...] = Field(min_length=1)

    @field_validator("tags", mode="after")
    @classmethod
    def _dedupe_sort(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(v)))


class MentionsAll(FrozenModel):
    iris: tuple[IRI, ...] = Field(min_length=1, max_length=8)

    @field_validator("iris", mode="after")
    @classmethod
    def _dedupe_sort(cls, v: tuple[IRI, ...]) -> tuple[IRI, ...]:
        return tuple(sorted(set(v)))


class MentionsAny(FrozenModel):
    iris: tuple[IRI, ...] = Field(min_length=1)

    @field_validator("iris", mode="after")
    @classmethod
    def _dedupe_sort(cls, v: tuple[IRI, ...]) -> tuple[IRI, ...]:
        return tuple(sorted(set(v)))


type AxiomConstraint = OfTypes | MentionsAll | MentionsAny | InSelection | AlwaysFalse
