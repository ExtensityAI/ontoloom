"""Output types of the axiom storage API."""

from collections import Counter
from dataclasses import dataclass

from ontoloom.hashing import HashedAxiom
from ontoloom.owl.annotations import Annotation


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
class AnnotateResult:
    """Result of `annotate_axiom`: the axiom plus the actually-applied deltas.

    `added` and `removed` reflect storage-level changes after dedup against
    existing annotations (so they may be smaller than the requested lists when
    callers send duplicates or removals for absent annotations).
    """

    hashed: HashedAxiom
    added: tuple[Annotation, ...]
    removed: tuple[Annotation, ...]


@dataclass(frozen=True, slots=True)
class RenameResult:
    old_iri: str
    new_iri: str
    replaced: tuple[ReplaceResult, ...]
    batch_id: str

    @property
    def colliding_hashes(self) -> tuple[str, ...]:
        """New hashes whose insertion was a no-op because an axiom with that hash already existed."""
        return tuple(sorted(r.new.hash for r in self.replaced if r.was_merged_into_existing))
