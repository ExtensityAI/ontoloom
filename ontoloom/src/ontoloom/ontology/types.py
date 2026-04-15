from collections import Counter
from dataclasses import dataclass
from typing import Literal

from ontoloom.ontology.models.axioms import Axiom
from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.literals import IRI

MatchSource = Literal["iri", "annotation", "list"]
MatchQuality = Literal["exact", "substring"]


@dataclass
class AnnotationRow:
    property: IRI
    value: str


@dataclass
class EntityInfo:
    roles: set[EntityType]
    annotations: list[AnnotationRow]
    axiom_counts: Counter[str]


@dataclass
class EntityMatch:
    iri: IRI
    roles: set[EntityType]
    annotations: list[AnnotationRow]
    match_source: MatchSource
    match_quality: MatchQuality


@dataclass
class EntitySearchPage:
    matches: list[EntityMatch]
    total: int


@dataclass
class HashedAxiom:
    axiom: Axiom
    hash: str


@dataclass
class SearchPage:
    axioms: list[HashedAxiom]
    total: int


@dataclass
class AddResult:
    added: list[HashedAxiom]
    skipped: list[HashedAxiom]


@dataclass
class RemoveResult:
    removed: list[HashedAxiom]
