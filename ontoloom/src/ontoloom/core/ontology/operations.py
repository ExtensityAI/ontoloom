"""Pure operations on Ontology. Each returns (new_ontology, metadata)."""

from __future__ import annotations

from dataclasses import dataclass

from ontoloom.core.ontology.models.axioms import Axiom
from ontoloom.core.ontology.models.ontology import Ontology


@dataclass(frozen=True)
class AddResult:
    """Metadata from an add operation."""

    added: tuple[Axiom, ...]
    skipped: tuple[Axiom, ...]


@dataclass(frozen=True)
class RemoveResult:
    """Metadata from a remove operation."""

    removed: tuple[Axiom, ...]


def add_axioms(ontology: Ontology, axioms: list[Axiom]):
    """Return a new ontology with axioms added. Duplicates (including within-batch) are skipped."""
    existing = set(ontology.axioms)
    added = list[Axiom]()
    skipped = list[Axiom]()

    for a in axioms:
        if a in existing:
            skipped.append(a)
        else:
            added.append(a)
            existing.add(a)

    new = Ontology(iri=ontology.iri, axioms=(*ontology.axioms, *added))
    return new, AddResult(added=tuple(added), skipped=tuple(skipped))


def remove_axioms(ontology: Ontology, axioms: set[Axiom]):
    """Return a new ontology with the given axioms removed. Axioms not found are ignored."""
    keep = list[Axiom]()
    removed = list[Axiom]()

    for a in ontology.axioms:
        (removed if a in axioms else keep).append(a)

    new = Ontology(iri=ontology.iri, axioms=tuple(keep))
    return new, RemoveResult(removed=tuple(removed))
