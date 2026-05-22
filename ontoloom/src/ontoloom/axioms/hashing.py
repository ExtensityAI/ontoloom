"""Content hashing for OWL 2 axioms -> identity by canonical content.

Hashes are SHA-256 of the canonical JSON form (see `canonical.py`). Two axioms
with the same logical content (modulo annotation differences and unordered-set
permutations) hash to the same value.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import override

from ontoloom.connection import Session
from ontoloom.errors import OntoloomError
from ontoloom.models import TypedStr
from ontoloom.utils import dquoted

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
            msg = f"AxiomHashPrefix must be hex chars, got {dquoted(value)}"
            raise ValueError(msg)
        return normalized


class AxiomHash(TypedStr):
    """Full 64-character lowercase hex SHA-256 digest of an axiom's canonical JSON."""

    description = "Full SHA-256 hex digest of an axiom (64 lowercase hex chars)"
    pattern = r"^[0-9a-f]{64}$"
    examples = ("0123456789abcdef" * 4,)

    @override
    @classmethod
    def parse(cls, value: str):
        normalized = value.lower()

        if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
            msg = f"AxiomHash must be 64 lowercase hex chars, got {dquoted(value)}"
            raise ValueError(msg)
        return normalized


def disambiguating_prefixes(hashes: Sequence[str]) -> list[str]:
    """Shortest prefix of each input string that uniquely identifies it. Order-preserving."""
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


class AxiomNotFoundError(OntoloomError):
    """No axiom matches the given hash prefix or full hash."""

    def __init__(self, needle: AxiomHashPrefix | AxiomHash):
        self.needle = needle
        super().__init__(f"No axiom matching hash [{needle}].")


class AmbiguousHashError(OntoloomError):
    """Hash prefix matches multiple axioms.

    `distinguishing_prefixes` are the minimum-length prefixes that uniquely
    identify each match -> the caller can copy any of them verbatim to retry.
    """

    def __init__(self, prefix: AxiomHashPrefix, count: int, distinguishing_prefixes: Sequence[str]):
        self.prefix = prefix
        self.count = count
        self.distinguishing_prefixes = distinguishing_prefixes
        max_shown = 10
        shown = ", ".join(distinguishing_prefixes[:max_shown])
        suffix = f", ... ({count - max_shown} more)" if count > max_shown else ""
        super().__init__(f"[{prefix}] matches {count} axioms: {shown}{suffix}.")


@dataclass(frozen=True, slots=True)
class ResolvedAxiom:
    axiom_id: int
    hash: AxiomHash
    json_data: str


def _prefix_upper_bound(prefix: str) -> str:
    """Lexicographic upper bound for `LIKE prefix || '%'` on a BINARY column.

    Increments the last character of the prefix by one code point. The prefix
    is constrained to lowercase hex by `AxiomHashPrefix`, so the increment
    never wraps past printable ASCII (`'9' -> ':'`, `'a' -> 'b'`, ...).
    """
    return prefix[:-1] + chr(ord(prefix[-1]) + 1)


def resolve_hash_prefix(s: Session, prefix: AxiomHashPrefix) -> AxiomHash:
    """Resolve a hash prefix to a full axiom hash; raise on missing or ambiguous.

    Mutation paths in core take `AxiomHash` directly; prefix → full resolution
    happens at the MCP boundary (or any other adapter that takes user input).
    """
    upper = _prefix_upper_bound(prefix)
    rows = s.conn.execute(
        "SELECT hash FROM axioms WHERE hash >= ? AND hash < ?",
        (prefix, upper),
    ).fetchall()
    if not rows:
        raise AxiomNotFoundError(prefix)
    if len(rows) > 1:
        full_hashes = [r[0] for r in rows]
        raise AmbiguousHashError(prefix, len(rows), disambiguating_prefixes(full_hashes))
    return AxiomHash(rows[0][0])


def load_axiom_row(s: Session, h: AxiomHash) -> ResolvedAxiom:
    """Fetch the row backing `h`. Raises AxiomNotFoundError if absent (race-safe)."""
    row = s.conn.execute("SELECT id, json(data) FROM axioms WHERE hash = ?", (h,)).fetchone()
    if row is None:
        raise AxiomNotFoundError(h)
    return ResolvedAxiom(axiom_id=row[0], hash=h, json_data=row[1])
