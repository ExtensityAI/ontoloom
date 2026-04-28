import importlib.resources
import sqlite3
import uuid
from pathlib import Path
from typing import Self

from ontoloom.ontology.errors import OntologyExistsError, OntologyNotFoundError

_SQL = importlib.resources.files("ontoloom.ontology")
_SCHEMA = _SQL.joinpath("schema.sql").read_text()
_PRAGMAS = _SQL.joinpath("pragmas.sql").read_text()


def _apply_pragmas(conn: sqlite3.Connection):
    was_autocommit = conn.autocommit
    conn.autocommit = True
    for line in _PRAGMAS.strip().splitlines():
        line = line.strip()
        if line:
            conn.execute(line)
    conn.autocommit = was_autocommit


def _migrate(conn: sqlite3.Connection):
    """Migrate schema for databases created before v3. Idempotent."""
    was_autocommit = conn.autocommit
    conn.autocommit = True

    # Events: add new columns and expand CHECK constraint
    event_cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    if "replaces_hash" not in event_cols:
        conn.execute("ALTER TABLE events RENAME TO _events_old")
        conn.execute(
            "CREATE TABLE events ("
            "  sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  session_id TEXT,"
            "  op TEXT NOT NULL CHECK (op IN ('add', 'del', 'replace', 'annotate')),"
            "  axiom_hash TEXT NOT NULL,"
            "  axiom_json BLOB,"
            "  replaces_hash TEXT,"
            "  annotation_diff TEXT,"
            "  batch_id TEXT,"
            "  timestamp TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        conn.execute(
            "INSERT INTO events (sequence_id, session_id, op, axiom_hash, axiom_json, timestamp)"
            " SELECT sequence_id, session_id, op, axiom_hash, axiom_json, timestamp FROM _events_old"
        )
        conn.execute("DROP TABLE _events_old")

    # Axioms: remove source column
    axiom_cols = {r[1] for r in conn.execute("PRAGMA table_info(axioms)")}
    if "source" in axiom_cols:
        conn.execute("ALTER TABLE axioms RENAME TO _axioms_old")
        conn.execute(
            "CREATE TABLE axioms ("
            "  id INTEGER PRIMARY KEY,"
            "  hash TEXT NOT NULL UNIQUE,"
            "  type TEXT NOT NULL,"
            "  data BLOB NOT NULL"
            ")"
        )
        conn.execute(
            "INSERT INTO axioms (id, hash, type, data) SELECT id, hash, type, data FROM _axioms_old"
        )
        conn.execute("DROP TABLE _axioms_old")

    # Selections: remove comment column
    sel_cols = {r[1] for r in conn.execute("PRAGMA table_info(selections)")}
    if "comment" in sel_cols:
        conn.execute("ALTER TABLE selections RENAME TO _selections_old")
        conn.execute(
            "CREATE TABLE selections ("
            "  name TEXT PRIMARY KEY,"
            "  kind TEXT NOT NULL CHECK (kind IN ('axioms', 'entities')),"
            "  hash TEXT NOT NULL,"
            "  cardinality INTEGER NOT NULL,"
            "  source TEXT NOT NULL,"
            "  created_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        conn.execute(
            "INSERT INTO selections (name, kind, hash, cardinality, source, created_at)"
            " SELECT name, kind, hash, cardinality, source, created_at FROM _selections_old"
        )
        conn.execute("DROP TABLE _selections_old")

    conn.autocommit = was_autocommit


class StoreNotOpenError(RuntimeError):
    pass


class Ontology:
    """Context manager for an open ontology database."""

    @classmethod
    def create(cls, path: Path) -> Self:
        """Create a new empty ontology database. Returns an unopened instance."""
        if path.exists():
            raise OntologyExistsError(path)
        conn = sqlite3.connect(str(path), autocommit=True)
        try:
            _apply_pragmas(conn)
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO metadata (id, data) VALUES (1, ?)",
                ('{"prefixes": {}}',),
            )
        finally:
            conn.close()
        return cls(path)

    def __init__(self, path: Path, *, session_id: str | None = None):
        """Reference an existing ontology. Raises OntologyNotFoundError if missing."""
        if not path.exists():
            raise OntologyNotFoundError(path)
        self._path = path
        self._session_id = session_id or uuid.uuid4().hex
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Active connection. Raises StoreNotOpenError if not inside `with` block."""
        if self._conn is None:
            msg = "Store is not open. Use `with Ontology(path) as ont:`."
            raise StoreNotOpenError(msg)
        return self._conn

    @property
    def session_id(self) -> str:
        return self._session_id

    def __enter__(self) -> Self:
        self._conn = sqlite3.connect(str(self._path), autocommit=False)
        _apply_pragmas(self._conn)
        _migrate(self._conn)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
