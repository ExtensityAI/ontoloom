"""Output types of the axiom storage API."""

from collections import Counter
from dataclasses import dataclass

from ontoloom.hashing import HashedAxiom


@dataclass(frozen=True, slots=True)
class AxiomSummary:
    total: int
    by_type: Counter[str]


@dataclass(frozen=True, slots=True)
class AddResult:
    added: tuple[HashedAxiom, ...]
    skipped: tuple[HashedAxiom, ...]


@dataclass(frozen=True, slots=True)
class RemoveResult:
    removed: tuple[HashedAxiom, ...]


@dataclass(frozen=True, slots=True)
class RemoveBySelectionResult:
    removed: tuple[HashedAxiom, ...]
    absent: int


@dataclass(frozen=True, slots=True)
class ReplaceResult:
    old: HashedAxiom
    new: HashedAxiom
    was_noop: bool  # True if new.hash == old.hash
    was_merged_into_existing: bool = False  # True if new_hash collided with another existing axiom

    @property
    def old_hash(self) -> str:
        return self.old.hash

    @property
    def new_hash(self) -> str:
        return self.new.hash


@dataclass(frozen=True, slots=True)
class RenameResult:
    old_iri: str
    new_iri: str
    replaced: tuple[ReplaceResult, ...]
    batch_id: str
