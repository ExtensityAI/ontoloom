"""Public run() — dispatches to per-query _run."""

from collections import Counter
from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import overload

from ontoloom.connection import Session
from ontoloom.entities.types import DuplicateResult
from ontoloom.hashing import AxiomHash
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query import (
    count_axioms_by_type,
    count_entities,
    count_entities_by_role,
    find_duplicate_entities,
    list_axiom_hashes,
    list_axioms,
    list_entities,
    read_axiom_selection,
    read_entity_selection,
    stream_axioms,
)
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.query.count_entities import CountEntities
from ontoloom.query.count_entities_by_role import CountEntitiesByRole
from ontoloom.query.find_duplicate_entities import FindDuplicateEntities
from ontoloom.query.list_axiom_hashes import ListAxiomHashes
from ontoloom.query.list_axioms import ListAxioms
from ontoloom.query.list_entities import ListEntities
from ontoloom.query.read_axiom_selection import ReadAxiomSelection
from ontoloom.query.read_entity_selection import ReadEntitySelection
from ontoloom.query.stream_axioms import StreamAxioms
from ontoloom.selections.types import AxiomSelectionPage, EntitySelectionPage

type AnyQuery = (
    CountEntities
    | ListEntities
    | CountEntitiesByRole
    | ListAxiomHashes
    | ListAxioms
    | CountAxiomsByType
    | StreamAxioms
    | ReadAxiomSelection
    | ReadEntitySelection
    | FindDuplicateEntities
)


@overload
def run(s: Session, q: CountEntities) -> int: ...
@overload
def run(s: Session, q: ListEntities) -> list[IRI]: ...
@overload
def run(s: Session, q: CountEntitiesByRole) -> Counter[EntityType]: ...
@overload
def run(s: Session, q: ListAxiomHashes) -> list[AxiomHash]: ...
@overload
def run(s: Session, q: ListAxioms) -> list[tuple[AxiomHash, str]]: ...
@overload
def run(s: Session, q: CountAxiomsByType) -> Counter[str]: ...
@overload
def run(s: Session, q: StreamAxioms) -> AbstractContextManager[Iterator[tuple[AxiomHash, str]]]: ...
@overload
def run(s: Session, q: ReadAxiomSelection) -> AxiomSelectionPage: ...
@overload
def run(s: Session, q: ReadEntitySelection) -> EntitySelectionPage: ...
@overload
def run(s: Session, q: FindDuplicateEntities) -> DuplicateResult: ...


def run(s: Session, q: AnyQuery) -> object:  # noqa: C901
    match q:
        case CountEntities():
            return count_entities._run(s, q)
        case ListEntities():
            return list_entities._run(s, q)
        case CountEntitiesByRole():
            return count_entities_by_role._run(s, q)
        case ListAxiomHashes():
            return list_axiom_hashes._run(s, q)
        case ListAxioms():
            return list_axioms._run(s, q)
        case CountAxiomsByType():
            return count_axioms_by_type._run(s, q)
        case StreamAxioms():
            return stream_axioms._run(s, q)
        case ReadAxiomSelection():
            return read_axiom_selection._run(s, q)
        case ReadEntitySelection():
            return read_entity_selection._run(s, q)
        case FindDuplicateEntities():
            return find_duplicate_entities._run(s, q)
        case _:
            msg = f"unknown query type: {type(q).__name__}"
            raise ValueError(msg)
