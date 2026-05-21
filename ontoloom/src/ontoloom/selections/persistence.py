"""Direct SQL CRUD on the `selections` and `selection_items` tables.

Core mutations do not perform optimistic-lock checks: callers needing
LLM-context staleness mitigation wrap mutations in `verify_lock` at the MCP
boundary. Multi-process callers need real transactions, not hash prefixes.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from ontoloom.connection import Session
from ontoloom.selections.types import (
    SelectionContentHash,
    SelectionKind,
    SelectionKindMismatchError,
    SelectionListing,
    SelectionMeta,
    SelectionName,
    SelectionNotFoundError,
    SelectionRef,
)
from ontoloom.utils import dedupe


@dataclass(frozen=True, slots=True)
class UpsertResult:
    selection: SelectionMeta
    previous_size: int | None


@dataclass(frozen=True, slots=True)
class DroppedSelection:
    name: SelectionName
    size: int


@dataclass(frozen=True, slots=True)
class RemoveSelectionsResult:
    dropped: tuple[DroppedSelection, ...]
    not_found: tuple[SelectionName, ...]


def _hash_selection_items(items: list[str]) -> SelectionContentHash:
    # Use ASCII Record Separator (\x1e) -> control char that cannot appear in
    # valid IRIs/CURIEs/hashes, so two distinct item sets never collide.
    # Empty `items` always produces the same hash (SHA-256 of ""). This is
    # correct: all empty selections have identical content. To distinguish two
    # empty selections by provenance, use the name, not the hash.
    content = "\x1e".join(sorted(items))
    return SelectionContentHash(hashlib.sha256(content.encode()).hexdigest()[:16])


def get_selection(s: Session, name: SelectionName) -> SelectionMeta:
    """Fetch selection metadata. Raises SelectionNotFoundError if absent."""
    row = s.conn.execute(
        "SELECT kind, hash, size, source FROM selections WHERE name = ?", (name,)
    ).fetchone()

    if row is None:
        raise SelectionNotFoundError(name)

    return SelectionMeta(
        name=name,
        kind=SelectionKind(row[0]),
        hash=SelectionContentHash(row[1]),
        size=row[2],
        source=row[3],
    )


def selection_exists(s: Session, name: SelectionName, kind: SelectionKind) -> bool:
    """True iff a selection row with the given name and kind exists."""
    row = s.conn.execute(
        "SELECT 1 FROM selections WHERE name = ? AND kind = ?",
        (name, kind),
    ).fetchone()
    return row is not None


def upsert_selection(
    s: Session,
    name: SelectionName,
    kind: SelectionKind,
    items: Sequence[str],
    source: str,
) -> UpsertResult:
    """Write a selection, overwriting if it exists.

    Caller's insertion order is preserved on disk (`id`, rowid alias); each
    Read* query chooses its own ordering — `ReadAxiomSelection` paginates in
    insertion order so any baked-in ranking survives, `ReadEntitySelection`
    paginates lexicographically. The content hash is order-independent (items
    sorted internally).

    Unconditional overwrite -> last writer wins, even if another agent has
    written since you last read. Optimistic locking (hash-prefix check) is a
    MCP-layer concern; callers needing it wrap this with `verify_lock`.
    """
    items = dedupe(items)
    content_hash = _hash_selection_items(items)
    size = len(items)

    existing = s.conn.execute(
        "SELECT size, hash FROM selections WHERE name = ?", (name,)
    ).fetchone()

    s.conn.execute("DELETE FROM selection_items WHERE selection_name = ?", (name,))
    s.conn.execute("DELETE FROM selections WHERE name = ?", (name,))
    s.conn.execute(
        "INSERT INTO selections (name, kind, hash, size, source) VALUES (?, ?, ?, ?, ?)",
        (name, kind, content_hash, size, source),
    )

    if items:
        s.conn.executemany(
            "INSERT INTO selection_items (selection_name, item) VALUES (?, ?)",
            [(name, item) for item in items],
        )

    return UpsertResult(
        selection=SelectionMeta(
            name=name,
            kind=kind,
            hash=content_hash,
            size=size,
            source=source,
        ),
        previous_size=existing[0] if existing else None,
    )


def list_selections(s: Session) -> list[SelectionListing]:
    """Return all selections paired with their current present-item count.

    Drift detection: `missing_count = meta.size - present_count`. Item is
    "present" iff it still resolves — for axiom selections, the hash exists in
    `axioms`; for entity selections, the IRI is referenced by any axiom
    (declared or not).
    """
    metas = [
        SelectionMeta(
            name=SelectionName(r[0]),
            kind=SelectionKind(r[1]),
            hash=r[2],
            size=r[3],
            source=r[4],
        )
        for r in s.conn.execute(
            "SELECT name, kind, hash, size, source FROM selections ORDER BY created_at, name"
        )
    ]

    if not metas:
        return []

    # Batched present-count queries — one per kind. Selections with zero items
    # produce count=0 via the LEFT JOIN's NULL row.
    axiom_present: dict[str, int] = dict(
        s.conn.execute(
            "SELECT s.name, COUNT(a.hash) "
            "FROM selections s "
            "LEFT JOIN selection_items si ON si.selection_name = s.name "
            "LEFT JOIN axioms a ON a.hash = si.item "
            "WHERE s.kind = ? "
            "GROUP BY s.name",
            (SelectionKind.AXIOMS.value,),
        )
    )
    entity_present: dict[str, int] = dict(
        s.conn.execute(
            "SELECT s.name, SUM(CASE WHEN EXISTS ("
            "SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item"
            ") THEN 1 ELSE 0 END) "
            "FROM selections s "
            "LEFT JOIN selection_items si ON si.selection_name = s.name "
            "WHERE s.kind = ? "
            "GROUP BY s.name",
            (SelectionKind.ENTITIES.value,),
        )
    )

    return [
        SelectionListing(
            meta=meta,
            present_count=(
                axiom_present.get(meta.name, 0)
                if meta.kind == SelectionKind.AXIOMS
                else entity_present.get(meta.name, 0)
            ),
        )
        for meta in metas
    ]


def _remove_by_names(s: Session, names: Sequence[SelectionName]) -> list[DroppedSelection]:
    """Delete the named selections in one batch; return what was actually dropped."""
    if not names:
        return []
    placeholders = ",".join("?" for _ in names)
    dropped = [
        DroppedSelection(name=SelectionName(r[0]), size=r[1])
        for r in s.conn.execute(
            f"SELECT name, size FROM selections WHERE name IN ({placeholders}) ORDER BY name",
            tuple(names),
        )
    ]
    if dropped:
        s.conn.execute(
            f"DELETE FROM selections WHERE name IN ({placeholders})",
            tuple(names),
        )
    return dropped


def remove_selections(s: Session, refs: Sequence[SelectionRef]) -> RemoveSelectionsResult:
    """Best-effort remove. Duplicate refs in the input are de-duplicated.

    Raises `SelectionKindMismatchError` if any ref's prefix disagrees with the
    stored kind (atomic precheck — nothing is removed on mismatch). Missing
    selections surface in `not_found`, not as an exception.
    """
    deduped = dedupe(refs)
    bare_names = [ref.bare for ref in deduped]

    if not bare_names:
        return RemoveSelectionsResult(dropped=(), not_found=())

    placeholders = ",".join("?" for _ in bare_names)
    stored_kinds: dict[str, str] = dict(
        s.conn.execute(
            f"SELECT name, kind FROM selections WHERE name IN ({placeholders})",
            bare_names,
        )
    )

    for ref in deduped:
        actual = stored_kinds.get(ref.bare)
        if actual is not None and actual != ref.kind.value:
            raise SelectionKindMismatchError(ref.bare, ref.kind, SelectionKind(actual))

    dropped = _remove_by_names(s, bare_names)
    found = {d.name for d in dropped}
    not_found = tuple(ref.bare for ref in deduped if ref.bare not in found)
    return RemoveSelectionsResult(dropped=tuple(dropped), not_found=not_found)
