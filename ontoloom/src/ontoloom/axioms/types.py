"""Output types of the axiom storage API."""

import hashlib
from collections import Counter
from dataclasses import dataclass

from ontoloom.axioms.hashing import AxiomHash, short_hash
from ontoloom.canonical import canonical_json
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import AxiomTag, BaseAxiom
from ontoloom.owl.iri import IRI
from ontoloom.selections.types import SelectionMeta


@dataclass(frozen=True, slots=True)
class HashedAxiom:
    """An axiom paired with its computed content hash."""

    axiom: BaseAxiom
    hash: AxiomHash

    @classmethod
    def of(cls, axiom: BaseAxiom):
        digest = hashlib.sha256(canonical_json(axiom).encode()).hexdigest()
        return cls(axiom=axiom, hash=AxiomHash(digest))

    @property
    def short(self):
        return short_hash(self.hash)


@dataclass(frozen=True, slots=True)
class AxiomSummary:
    total: int
    by_type: Counter[AxiomTag]


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
    meta: SelectionMeta


@dataclass(frozen=True, slots=True)
class ReplaceResult:
    old: HashedAxiom
    new: HashedAxiom
    was_noop: bool  # True if new.hash == old.hash
    was_merged_into_existing: bool = False  # True if new_hash collided with another existing axiom


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
    old_iri: IRI
    new_iri: IRI
    replaced: tuple[ReplaceResult, ...]

    @property
    def colliding_hashes(self) -> tuple[AxiomHash, ...]:
        """New hashes whose insertion was a no-op because an axiom with that hash already existed."""
        return tuple(sorted(r.new.hash for r in self.replaced if r.was_merged_into_existing))
