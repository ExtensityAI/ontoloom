"""Regression: SQLite WAL + the project's explicit-BEGIN session pattern closes
the lost-update window between a session's first read and its subsequent write.

If a competing connection commits a write *anywhere* between session A's first
read and A's commit, A's commit fails with `database is locked` (snapshot
conflict). A's write does not silently overwrite the competitor's change.
"""

import sqlite3
from pathlib import Path

import pytest
from ontoloom.connection import Ontology, session
from ontoloom.errors import ConcurrentWriteError
from ontoloom.selections.store import upsert_entity_selection
from ontoloom.selections.types import SelectionName

_PRAGMAS = (Path(__file__).parent.parent / "src" / "ontoloom" / "sql" / "pragmas.sql").read_text()


def _raw(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), autocommit=True)
    conn.executescript(_PRAGMAS)
    return conn


def test_wal_snapshot_isolation_prevents_lost_update_toctou(tmp_path):
    """A's initial SELECT pins A's snapshot; if B commits anything before A
    commits, A's write fails — even when A writes a different row."""
    db = tmp_path / "iso.db"
    ont = Ontology.create(db)

    with session(ont) as s:
        upsert_entity_selection(s, SelectionName("foo"), ["ex:Initial"], "seed")
        s.commit()

    raw_a = _raw(db)
    raw_b = _raw(db)
    try:
        # A: BEGIN + initial read (snapshot established).
        raw_a.execute("BEGIN")
        raw_a.execute("SELECT hash FROM entity_selections WHERE name = 'foo'").fetchone()

        # B: concurrent writer commits an overwrite of `foo`.
        raw_b.execute("BEGIN IMMEDIATE")
        raw_b.execute("DELETE FROM entity_selection_items WHERE selection_name = 'foo'")
        raw_b.execute("DELETE FROM entity_selections WHERE name = 'foo'")
        raw_b.execute(
            "INSERT INTO entity_selections (name, hash, size, source) VALUES (?, ?, ?, ?)",
            ("foo", "deadbeefdeadbeef", 1, "B-write"),
        )
        raw_b.execute("COMMIT")

        # A: any write now fails — snapshot conflict.
        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
            raw_a.execute("DELETE FROM entity_selections WHERE name = 'foo'")
            raw_a.execute("COMMIT")
    finally:
        raw_a.close()
        raw_b.close()

    # B's write is the persisted state — no corruption.
    final = sqlite3.connect(str(db), autocommit=True)
    row = final.execute("SELECT source FROM entity_selections WHERE name = 'foo'").fetchone()
    final.close()
    assert row[0] == "B-write"


def test_session_translates_snapshot_conflict_to_concurrent_write_error(tmp_path):
    """Snapshot conflict inside `session()` surfaces as `ConcurrentWriteError`,
    not raw `sqlite3.OperationalError`, so MCP callers get an actionable message."""
    db = tmp_path / "iso.db"
    ont = Ontology.create(db)

    with session(ont) as s:
        upsert_entity_selection(s, SelectionName("foo"), ["ex:Initial"], "seed")
        s.commit()

    raw_b = _raw(db)
    try:
        with pytest.raises(ConcurrentWriteError, match="locked"), session(ont) as a:
            # A pins its snapshot with an initial read.
            a.conn.execute("SELECT hash FROM entity_selections WHERE name = 'foo'").fetchone()

            # B commits an overwrite under A's snapshot.
            raw_b.execute("BEGIN IMMEDIATE")
            raw_b.execute("DELETE FROM entity_selection_items WHERE selection_name = 'foo'")
            raw_b.execute("DELETE FROM entity_selections WHERE name = 'foo'")
            raw_b.execute(
                "INSERT INTO entity_selections (name, hash, size, source) VALUES (?, ?, ?, ?)",
                ("foo", "deadbeefdeadbeef", 1, "B-write"),
            )
            raw_b.execute("COMMIT")

            # A's first write hits the snapshot conflict -> translated.
            a.conn.execute("DELETE FROM entity_selections WHERE name = 'foo'")
            a.commit()
    finally:
        raw_b.close()
