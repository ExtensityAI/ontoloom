"""Direct SQL CRUD on the kind-specific selection tables.

Two parallel families operate on `axiom_selections` / `axiom_selection_items`
and `entity_selections` / `entity_selection_items` respectively. The two kinds
never share storage — every callsite knows its kind statically.

Core mutations do not perform optimistic-lock checks: callers needing
LLM-context staleness mitigation wrap mutations in `verify_lock` at the MCP
boundary. Multi-process callers need real transactions, not hash prefixes.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from ontoloom.connection import Session
from ontoloom.selections.types import (
    AxiomSelection,
    AxiomSelectionListing,
    AxiomSelectionName,
    EntitySelection,
    EntitySelectionListing,
    EntitySelectionName,
    SelectionContentHash,
    SelectionExistsError,
    SelectionName,
    SelectionNotFoundError,
    WriteMode,
)
from ontoloom.utils import dedupe


@dataclass(frozen=True, slots=True)
class AxiomUpsertResult:
    selection: AxiomSelection
    previous_size: int | None


@dataclass(frozen=True, slots=True)
class EntityUpsertResult:
    selection: EntitySelection
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


# -- Axiom-side --


def get_axiom_selection(s: Session, name: SelectionName) -> AxiomSelection:
    """Fetch axiom-selection metadata. Raises SelectionNotFoundError if absent."""
    row = s.conn.execute(
        "SELECT hash, size, source FROM axiom_selections WHERE name = ?", (name,)
    ).fetchone()

    if row is None:
        raise SelectionNotFoundError(name)

    return AxiomSelection(
        name=name,
        hash=SelectionContentHash(row[0]),
        size=row[1],
        source=row[2],
    )


def axiom_selection_exists(s: Session, name: SelectionName) -> bool:
    """True iff an axiom-selection row with the given name exists."""
    row = s.conn.execute("SELECT 1 FROM axiom_selections WHERE name = ?", (name,)).fetchone()
    return row is not None


def upsert_axiom_selection(
    s: Session,
    name: SelectionName,
    items: Sequence[str],
    source: str,
    mode: WriteMode = WriteMode.CREATE,
) -> AxiomUpsertResult:
    """Write an axiom selection.

    `mode=CREATE` (default) refuses to clobber an occupied name, raising
    `SelectionExistsError`. `mode=REPLACE` overwrites unconditionally ->
    last writer wins, even if another agent has written since you last read.

    Caller's insertion order is preserved on disk (`id`, rowid alias);
    `ReadAxiomSelection` paginates in insertion order so any baked-in ranking
    survives. The content hash is order-independent (items sorted internally).

    Optimistic locking (hash-prefix check) is a MCP-layer concern; callers
    needing it wrap this with `verify_lock`.

    Raises:
        SelectionExistsError: `mode=CREATE` and the name is already in use.
    """
    deduped = dedupe(items)
    content_hash = _hash_selection_items(deduped)
    size = len(deduped)

    existing = s.conn.execute(
        "SELECT size FROM axiom_selections WHERE name = ?", (name,)
    ).fetchone()

    if existing is not None and mode is WriteMode.CREATE:
        raise SelectionExistsError(name, existing[0])

    s.conn.execute("DELETE FROM axiom_selection_items WHERE selection_name = ?", (name,))
    s.conn.execute("DELETE FROM axiom_selections WHERE name = ?", (name,))
    s.conn.execute(
        "INSERT INTO axiom_selections (name, hash, size, source) VALUES (?, ?, ?, ?)",
        (name, content_hash, size, source),
    )

    if deduped:
        s.conn.executemany(
            "INSERT INTO axiom_selection_items (selection_name, item) VALUES (?, ?)",
            [(name, item) for item in deduped],
        )

    return AxiomUpsertResult(
        selection=AxiomSelection(
            name=name,
            hash=content_hash,
            size=size,
            source=source,
        ),
        previous_size=existing[0] if existing else None,
    )


def list_axiom_selections(s: Session) -> list[AxiomSelectionListing]:
    """Return all axiom selections paired with their current present-item count.

    An axiom item is "present" iff its hash still exists in the `axioms` table.
    """
    metas = [
        AxiomSelection(
            name=SelectionName(r[0]),
            hash=SelectionContentHash(r[1]),
            size=r[2],
            source=r[3],
        )
        for r in s.conn.execute(
            "SELECT name, hash, size, source FROM axiom_selections ORDER BY created_at, name"
        )
    ]

    if not metas:
        return []

    present: dict[str, int] = dict(
        s.conn.execute(
            "SELECT s.name, COUNT(a.hash) "
            "FROM axiom_selections s "
            "LEFT JOIN axiom_selection_items si ON si.selection_name = s.name "
            "LEFT JOIN axioms a ON a.hash = si.item "
            "GROUP BY s.name"
        )
    )

    return [
        AxiomSelectionListing(meta=meta, present_count=present.get(meta.name, 0)) for meta in metas
    ]


def remove_axiom_selections(
    s: Session, names: Sequence[AxiomSelectionName]
) -> RemoveSelectionsResult:
    """Best-effort remove. Duplicate refs in the input are de-duplicated.

    Missing selections surface in `not_found`, not as an exception.
    """
    bare_names = dedupe(ref.bare for ref in names)
    return _remove_named(s, "axiom_selections", bare_names)


def get_axiom_selection_items(s: Session, name: SelectionName) -> list[str]:
    """Read the items of an axiom selection in insertion order."""
    return [
        r[0]
        for r in s.conn.execute(
            "SELECT item FROM axiom_selection_items WHERE selection_name = ? ORDER BY id",
            (name,),
        )
    ]


# -- Entity-side (mirror) --


def get_entity_selection(s: Session, name: SelectionName) -> EntitySelection:
    """Fetch entity-selection metadata. Raises SelectionNotFoundError if absent."""
    row = s.conn.execute(
        "SELECT hash, size, source FROM entity_selections WHERE name = ?", (name,)
    ).fetchone()

    if row is None:
        raise SelectionNotFoundError(name)

    return EntitySelection(
        name=name,
        hash=SelectionContentHash(row[0]),
        size=row[1],
        source=row[2],
    )


def entity_selection_exists(s: Session, name: SelectionName) -> bool:
    """True iff an entity-selection row with the given name exists."""
    row = s.conn.execute("SELECT 1 FROM entity_selections WHERE name = ?", (name,)).fetchone()
    return row is not None


def upsert_entity_selection(
    s: Session,
    name: SelectionName,
    items: Sequence[str],
    source: str,
    mode: WriteMode = WriteMode.CREATE,
) -> EntityUpsertResult:
    """Write an entity selection.

    `mode=CREATE` (default) refuses to clobber an occupied name, raising
    `SelectionExistsError`. `mode=REPLACE` overwrites unconditionally ->
    last writer wins.

    Caller's insertion order is preserved on disk; `ReadEntitySelection`
    paginates lexicographically on the IRI. The content hash is
    order-independent (items sorted internally).

    Optimistic locking is a MCP-layer concern; callers needing it wrap this
    with `verify_lock`.

    Raises:
        SelectionExistsError: `mode=CREATE` and the name is already in use.
    """
    deduped = dedupe(items)
    content_hash = _hash_selection_items(deduped)
    size = len(deduped)

    existing = s.conn.execute(
        "SELECT size FROM entity_selections WHERE name = ?", (name,)
    ).fetchone()

    if existing is not None and mode is WriteMode.CREATE:
        raise SelectionExistsError(name, existing[0])

    s.conn.execute("DELETE FROM entity_selection_items WHERE selection_name = ?", (name,))
    s.conn.execute("DELETE FROM entity_selections WHERE name = ?", (name,))
    s.conn.execute(
        "INSERT INTO entity_selections (name, hash, size, source) VALUES (?, ?, ?, ?)",
        (name, content_hash, size, source),
    )

    if deduped:
        s.conn.executemany(
            "INSERT INTO entity_selection_items (selection_name, item) VALUES (?, ?)",
            [(name, item) for item in deduped],
        )

    return EntityUpsertResult(
        selection=EntitySelection(
            name=name,
            hash=content_hash,
            size=size,
            source=source,
        ),
        previous_size=existing[0] if existing else None,
    )


def list_entity_selections(s: Session) -> list[EntitySelectionListing]:
    """Return all entity selections paired with their current present-item count.

    An entity item is "present" iff its IRI is referenced by any axiom
    (declared or not).
    """
    metas = [
        EntitySelection(
            name=SelectionName(r[0]),
            hash=SelectionContentHash(r[1]),
            size=r[2],
            source=r[3],
        )
        for r in s.conn.execute(
            "SELECT name, hash, size, source FROM entity_selections ORDER BY created_at, name"
        )
    ]

    if not metas:
        return []

    present: dict[str, int] = dict(
        s.conn.execute(
            "SELECT s.name, SUM(CASE WHEN EXISTS ("
            "SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item"
            ") THEN 1 ELSE 0 END) "
            "FROM entity_selections s "
            "LEFT JOIN entity_selection_items si ON si.selection_name = s.name "
            "GROUP BY s.name"
        )
    )

    return [
        EntitySelectionListing(meta=meta, present_count=present.get(meta.name, 0) or 0)
        for meta in metas
    ]


def remove_entity_selections(
    s: Session, names: Sequence[EntitySelectionName]
) -> RemoveSelectionsResult:
    """Best-effort remove. Duplicate refs in the input are de-duplicated.

    Missing selections surface in `not_found`, not as an exception.
    """
    bare_names = dedupe(ref.bare for ref in names)
    return _remove_named(s, "entity_selections", bare_names)


def get_entity_selection_items(s: Session, name: SelectionName) -> list[str]:
    """Read the items of an entity selection in insertion order."""
    return [
        r[0]
        for r in s.conn.execute(
            "SELECT item FROM entity_selection_items WHERE selection_name = ? ORDER BY id",
            (name,),
        )
    ]


# -- shared low-level helper --


def _remove_named(
    s: Session, table: str, bare_names: Sequence[SelectionName]
) -> RemoveSelectionsResult:
    if not bare_names:
        return RemoveSelectionsResult(dropped=(), not_found=())

    placeholders = ",".join("?" for _ in bare_names)
    dropped = [
        DroppedSelection(name=SelectionName(r[0]), size=r[1])
        for r in s.conn.execute(
            f"SELECT name, size FROM {table} WHERE name IN ({placeholders}) ORDER BY name",
            tuple(bare_names),
        )
    ]
    if dropped:
        s.conn.execute(
            f"DELETE FROM {table} WHERE name IN ({placeholders})",
            tuple(bare_names),
        )
    found = {d.name for d in dropped}
    not_found = tuple(n for n in bare_names if n not in found)
    return RemoveSelectionsResult(dropped=tuple(dropped), not_found=not_found)
