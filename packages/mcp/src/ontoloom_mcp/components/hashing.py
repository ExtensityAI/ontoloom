"""Axiom hashing, unique prefix computation, and hash-prefix resolution."""

from __future__ import annotations

import hashlib
from typing import NamedTuple

from fastmcp.exceptions import ToolError
from ontoloom.core.ontology.models.axioms import Axiom
from pydantic import BaseModel

MIN_PREFIX_LEN = 4
_MAX_PREFIX_LEN = 64


class HashedAxiom(NamedTuple):
    """An axiom paired with its full hash and shortest unique prefix."""

    axiom: Axiom
    hash: str
    prefix: str


def _sha256(axiom: Axiom) -> str:
    return hashlib.sha256(axiom.model_dump_json().encode()).hexdigest()


def _common_prefix_len(a: str, b: str) -> int:
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return i


def _unique_prefix_lens(hashes: list[str]) -> list[int]:
    """Compute the shortest unique prefix length for each hash."""
    if not hashes:
        return []

    indexed = sorted(enumerate(hashes), key=lambda t: t[1])
    prefix_lens = [MIN_PREFIX_LEN] * len(hashes)

    for rank, (idx, h) in enumerate(indexed):
        needed = prefix_lens[idx]
        for neighbour_rank in (rank - 1, rank + 1):
            if 0 <= neighbour_rank < len(indexed):
                common = _common_prefix_len(h, indexed[neighbour_rank][1])
                needed = max(needed, common + 1)
        prefix_lens[idx] = min(needed, _MAX_PREFIX_LEN)

    return prefix_lens


def compute_hashes(axioms: tuple[Axiom, ...]) -> list[HashedAxiom]:
    """Compute hashes and shortest unique prefixes for a set of axioms."""
    hashes = [_sha256(a) for a in axioms]
    prefix_lens = _unique_prefix_lens(hashes)
    return [HashedAxiom(a, h, h[:pl]) for a, h, pl in zip(axioms, hashes, prefix_lens, strict=True)]


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


def resolve_axiom_ids(hashed: list[HashedAxiom], prefixes: list[str]) -> list[ResolveResult]:
    """Resolve user-provided hash prefixes to axioms."""
    results = list[ResolveResult]()

    for prefix in prefixes:
        matches = [(i, ha) for i, ha in enumerate(hashed) if ha.hash.startswith(prefix)]

        if len(matches) == 0:
            results.append(NotFound(prefix=prefix))

        elif len(matches) == 1:
            idx, ha = matches[0]
            results.append(ExactMatch(prefix=prefix, index=idx, axiom=ha.axiom))

        else:
            colliding_hashes = [ha.hash for _, ha in matches]
            candidate_prefix_lens = _unique_prefix_lens(colliding_hashes)

            candidates = [
                Candidate(
                    prefix=colliding_hashes[rank][: candidate_prefix_lens[rank]],
                    index=idx,
                    axiom=ha.axiom,
                )
                for rank, (idx, ha) in enumerate(matches)
            ]
            results.append(AmbiguousMatch(prefix=prefix, candidates=candidates))

    return results


def resolve_or_raise(hashed: list[HashedAxiom], prefixes: list[str]) -> list[ExactMatch]:
    """Resolve hash prefixes to axioms, raising ToolError if any fail."""
    results = resolve_axiom_ids(hashed, prefixes)
    errors = [r for r in results if not isinstance(r, ExactMatch)]
    if errors:
        raise ToolError("\n\n".join(str(e) for e in errors))
    return [r for r in results if isinstance(r, ExactMatch)]
