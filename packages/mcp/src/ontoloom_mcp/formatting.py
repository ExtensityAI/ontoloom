"""Axiom hashing, prefix computation, and compact formatting for MCP output."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import get_args

from ontoloom.core.ontology.models.axioms import Axiom
from pydantic import BaseModel

MIN_PREFIX_LEN = 4
"""Minimum prefix length used to display hashes. Values lower than 4 likely produce many collisions."""

_MAX_PREFIX_LEN = 64  # sha256 hex digest len


# =============================================================================
# Resolution result types
# =============================================================================


class Candidate(BaseModel):
    """An axiom candidate in an ambiguous match, with a disambiguating prefix."""

    prefix: str
    index: int
    axiom: Axiom


class ExactMatch(BaseModel):
    """Prefix matched exactly one axiom."""

    prefix: str
    index: int
    axiom: Axiom


class NotFound(BaseModel):
    """No axiom matched the given prefix."""

    prefix: str

    def __str__(self) -> str:
        return f"[{self.prefix}] not found"


class AmbiguousMatch(BaseModel):
    """Multiple axioms matched the given prefix."""

    prefix: str
    candidates: list[Candidate]

    def __str__(self) -> str:
        lines = [f"  [{c.prefix}] {c.axiom}" for c in self.candidates]
        return f"[{self.prefix}] matches {len(self.candidates)} axioms:\n" + "\n".join(lines)


type ResolveResult = ExactMatch | NotFound | AmbiguousMatch


# =============================================================================
# Hashing
# =============================================================================


def compute_axiom_hash(axiom: Axiom):
    """Compute a stable SHA-256 hex digest for an axiom."""
    return hashlib.sha256(axiom.model_dump_json().encode()).hexdigest()


# =============================================================================
# Prefix computation
# =============================================================================


def _compute_common_prefix_len(a: str, b: str):
    """Number of leading characters shared by two strings."""
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return i


def compute_unique_prefix_lens(hashes: list[str]) -> list[int]:
    """Compute the shortest unique hash prefix length for each hash.
    Returns a list parallel to the input list.
    """
    if not hashes:
        return []

    # (hash, original_index) sorted by hash -- collisions are adjacent
    indexed = sorted(enumerate(hashes), key=lambda t: t[1])

    prefix_lens = [MIN_PREFIX_LEN] * len(hashes)

    for rank, (idx, h) in enumerate(indexed):
        needed = prefix_lens[idx]

        for neighbour_rank in (rank - 1, rank + 1):
            if neighbour_rank < 0 or neighbour_rank >= len(indexed):
                continue

            _, neighbour_hash = indexed[neighbour_rank]
            common = _compute_common_prefix_len(h, neighbour_hash)
            needed = max(needed, common + 1)

        prefix_lens[idx] = min(needed, _MAX_PREFIX_LEN)

    return prefix_lens


# =============================================================================
# Formatting
# =============================================================================


type DiffEntry = tuple[str, Axiom]  # ("+", axiom) or ("=", axiom) or ("-", axiom)


def format_diff(entries: list[DiffEntry], summary: str):
    """Format a diff with a summary and tagged axiom lines."""
    changes = "\n".join(f"{tag} {a}" for tag, a in entries)
    return f"{summary}\n\n```diff\n{changes}\n```"


AXIOM_TYPE_NAMES: tuple[str] = tuple(
    cls.model_fields["type"].default for cls in get_args(get_args(Axiom)[0])
)
"""Names of all axiom types"""


def format_axiom_summary(axioms: tuple[Axiom, ...]):
    """Render axiom count statistics: total + breakdown by type, sorted descending."""
    counts = Counter(a.type for a in axioms)

    # Ensure all types appear, sorted by count descending then alphabetically
    rows = sorted(AXIOM_TYPE_NAMES, key=lambda t: (-counts[t], t))
    lines = [f"{len(axioms)} axioms total"]
    lines.extend(f"  {counts[t]} {t}" for t in rows)
    return "\n".join(lines)


def format_axiom_listing(axioms: tuple[Axiom, ...]):
    """Render axioms as compact lines with shortest-unique hash prefixes."""
    if not axioms:
        return ""

    # TODO: simplify all this - do we need separate funcs everywhere?
    hashes = [compute_axiom_hash(a) for a in axioms]
    prefix_lens = compute_unique_prefix_lens(hashes)
    lines = [f"[{hashes[i][: prefix_lens[i]]}] {a}" for i, a in enumerate(axioms)]
    return "\n".join(lines)


# =============================================================================
# Resolution
# =============================================================================


def resolve_axiom_ids(axioms: tuple[Axiom, ...], prefixes: list[str]):
    """Resolve hash prefixes to axioms.

    Returns one result per input prefix: ExactMatch, NotFound, or AmbiguousMatch.
    AmbiguousMatch candidates include disambiguating prefixes computed to be
    unique within the collision group.
    """
    hashes = [compute_axiom_hash(a) for a in axioms]
    results = list[ResolveResult]()

    for prefix in prefixes:
        matches = [
            (i, a)
            for i, (a, h) in enumerate(zip(axioms, hashes, strict=False))
            if h.startswith(prefix)
        ]

        if len(matches) == 0:
            # prefix not found
            results.append(NotFound(prefix=prefix))

        elif len(matches) == 1:
            # found exactly one axiom
            idx, axiom = matches[0]
            results.append(ExactMatch(prefix=prefix, index=idx, axiom=axiom))
        else:
            # found multiple axioms!
            # Compute disambiguating prefixes scoped to the collision group
            colliding_hashes = [hashes[i] for i, _ in matches]
            candidate_prefix_lens = compute_unique_prefix_lens(colliding_hashes)

            candidates = [
                Candidate(
                    prefix=colliding_hashes[rank][: candidate_prefix_lens[rank]],
                    index=idx,
                    axiom=axiom,
                )
                for rank, (idx, axiom) in enumerate(matches)
            ]

            results.append(AmbiguousMatch(prefix=prefix, candidates=candidates))

    return results
