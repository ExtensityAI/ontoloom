"""Public data types returned by OntologyStore methods."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ontoloom.core.ontology.models.axioms import Axiom
from ontoloom.core.ontology.models.base import EntityType
from ontoloom.core.ontology.models.literals import IRI


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
    match_source: str
    match_quality: str


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
