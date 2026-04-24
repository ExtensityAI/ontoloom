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
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
