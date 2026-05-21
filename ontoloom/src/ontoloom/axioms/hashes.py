from collections.abc import Sequence
from dataclasses import dataclass

from ontoloom.connection import Session
from ontoloom.errors import OntoloomError
from ontoloom.hashing import (
    AxiomHash,
    AxiomHashPrefix,
    disambiguating_prefixes,
)


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
