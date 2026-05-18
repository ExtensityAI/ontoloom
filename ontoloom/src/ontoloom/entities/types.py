"""Output types of the entity storage API."""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import AxiomTag, EntityType


class MatchSource(StrEnum):
    """Where in the entity record a text-search query matched."""

    IRI = "iri"
    ANNOTATION = "annotation"
    LIST = "list"


class MatchQuality(StrEnum):
    """How the text-search query matched."""

    EXACT = "exact"
    SUBSTRING = "substring"


@dataclass(frozen=True, slots=True)
class AnnotationRow:
    property: IRI
    value: str


@dataclass(frozen=True, slots=True)
class EntitySummary:
    total: int
    by_role: Counter[EntityType]


@dataclass(frozen=True, slots=True)
class EntityInfo:
    roles: frozenset[EntityType]
    annotations: tuple[AnnotationRow, ...]
    axiom_counts: Counter[AxiomTag]


@dataclass(frozen=True, slots=True)
class EntityMatch:
    iri: IRI
    roles: frozenset[EntityType]
    annotations: tuple[AnnotationRow, ...]
    match_source: MatchSource
    match_quality: MatchQuality


@dataclass(frozen=True, slots=True)
class EntitySearchPage:
    matches: tuple[EntityMatch, ...]
    total: int
    offset: int


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    value: str
    iris: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DuplicateResult:
    groups: tuple[DuplicateGroup, ...]
    total_groups: int
    affected_iris: tuple[str, ...]
