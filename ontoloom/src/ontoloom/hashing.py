"""Content hashing for OWL 2 axioms -> identity by canonical content.

Hashes are SHA-256 of the canonical JSON form (see `canonical.py`). Two axioms
with the same logical content (modulo annotation differences and unordered-set
permutations) hash to the same value.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import override

from ontoloom.canonical import canonical_json
from ontoloom.models import TypedStr
from ontoloom.owl.axioms import BaseAxiom

# Standard width for hash prefixes shown to users. 12 hex chars = 48 bits;
# collision probability stays under 0.02% even at 10M axioms (SNOMED CT scale).
HASH_DISPLAY_LEN = 12


def short_hash(h: str) -> str:
    return h[:HASH_DISPLAY_LEN]


class AxiomHashPrefix(TypedStr):
    """Hex prefix of an axiom content hash. Lowercased on construction; may be ambiguous."""

    description = "Hex prefix of an axiom content hash"
    pattern = r"^[0-9a-fA-F]+$"
    examples = ("a3f1b2c4", "abc123def456")

    @override
    @classmethod
    def parse(cls, value: str):
        normalized = value.lower()

        if not normalized:
            msg = "AxiomHashPrefix must not be empty"
            raise ValueError(msg)
        if any(c not in "0123456789abcdef" for c in normalized):
            msg = f"AxiomHashPrefix must be hex chars, got {value!r}"
            raise ValueError(msg)
        return normalized


@dataclass(frozen=True, slots=True)
class HashedAxiom:
    """An axiom paired with its computed content hash."""

    axiom: BaseAxiom
    hash: str

    @classmethod
    def of(cls, axiom: BaseAxiom):
        digest = hashlib.sha256(canonical_json(axiom).encode()).hexdigest()
        return cls(axiom=axiom, hash=digest)

    @property
    def short(self):
        return short_hash(self.hash)


def disambiguating_prefixes(hashes: Sequence[str]) -> list[str]:
    """Shortest prefix of each hash that uniquely identifies it within the set.

    Used by AmbiguousHashError to tell the caller exactly how much they need to
    extend their prefix. Returns prefixes in input order.
    """
    if len(hashes) == 1:
        return [hashes[0]]

    indexed = sorted(enumerate(hashes), key=lambda p: p[1])
    out: list[str] = [""] * len(hashes)

    for rank, (orig_idx, h) in enumerate(indexed):
        lcp = 0

        if rank > 0:
            lcp = max(lcp, _lcp_len(h, indexed[rank - 1][1]))
        if rank < len(indexed) - 1:
            lcp = max(lcp, _lcp_len(h, indexed[rank + 1][1]))

        out[orig_idx] = h[: lcp + 1]
    return out


def _lcp_len(a: str, b: str):
    n = 0

    for x, y in zip(a, b, strict=False):
        if x != y:
            return n
        n += 1
    return n
