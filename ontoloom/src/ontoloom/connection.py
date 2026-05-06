import importlib.resources
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Self

from ontoloom.errors import BadRequestError, OntoloomError
from ontoloom.models import FrozenModel

_SQL = importlib.resources.files("ontoloom").joinpath("sql")
_SCHEMA = _SQL.joinpath("schema.sql").read_text()
_PRAGMAS = _SQL.joinpath("pragmas.sql").read_text()

CURRENT_SCHEMA_VERSION = 3


# Optional sandbox root for agent-supplied paths. Set `ONTOLOOM_WORKSPACE_ROOT`
# to confine `Ontology(...)` and `export.to_jsonl`/`import_jsonl`. Unset (default)
# means unrestricted, preserving single-user behavior.
_env = os.environ.get("ONTOLOOM_WORKSPACE_ROOT")
WORKSPACE_ROOT = Path(_env).resolve() if _env else None


# A: add small doc
def assert_within_workspace(path: Path):
    if WORKSPACE_ROOT is None:
        return
    if not path.resolve().is_relative_to(WORKSPACE_ROOT):
        msg = f"Path {path!s} is outside the configured workspace ({WORKSPACE_ROOT})."
        raise BadRequestError(msg)


# A: maybe add a sentinel value or sth, s.t. we know that this is unambiguously ontoloom into the schema? then we can drop all the required tables and other machinery, I do not like it.
class Metadata(FrozenModel):
    """Typed shape of the singleton row in the `metadata` table."""

    prefixes: dict[str, str]
    schema_version: int


_REQUIRED_TABLES = frozenset(
    {
        "axiom_entities",
        "axiom_text",
        "axioms",
        "entity_text",
        "events",
        "metadata",
        "selection_items",
        "selections",
    }
)

# Backslash chosen as the LIKE-ESCAPE character; pair every use with `ESCAPE '\\'`.
LIKE_ESCAPE = "\\"


# A: do we really need to escape like and other meta chars? is this secure?
def escape_like(value: str):
    """Escape SQL LIKE metacharacters (`\\`, `%`, `_`) so a parameter is matched literally.
    Use with `LIKE ? ESCAPE '\\'`.
    """
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


# A: inline
def _apply_pragmas(conn: sqlite3.Connection):
    # executescript handles SQL parsing (multi-line statements, comments) properly;
    # the previous line-by-line splitter would silently break on either.
    conn.executescript(_PRAGMAS)


# A: drop after adding the sentinel as seen above, we can then just check if metadata contains it and else error
def _validate_schema(conn: sqlite3.Connection):
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    missing = _REQUIRED_TABLES - existing
    if missing:
        msg = (
            f"Not an ontoloom database or schema is incomplete (missing tables: {sorted(missing)})"
        )
        raise OntologySchemaError(msg)
    row = conn.execute(
        "SELECT json_extract(data, '$.schema_version') FROM metadata WHERE id = 1"
    ).fetchone()
    stored = row[0] if row else None
    if stored != CURRENT_SCHEMA_VERSION:
        msg = f"Schema version mismatch: expected {CURRENT_SCHEMA_VERSION}, got {stored!r}"
        raise OntologySchemaError(msg)


class OntologyNotFoundError(OntoloomError, FileNotFoundError):
    """Ontology database file does not exist."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"'{path}' does not exist.")


class OntologyExistsError(OntoloomError, FileExistsError):
    """Ontology database file already exists."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"'{path}' already exists.")


class OntologySchemaError(OntoloomError):
    """Database is not an ontoloom store or its schema version does not match."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


# A: need a doc
class StoreNotOpenError(RuntimeError):
    pass


class Ontology:
    # A: should only explain what this is, doc seems more like it should be a comment!
    """Context manager for an open ontology database.

    Single-use within one thread. `__enter__`/`__exit__` may be called multiple
    times sequentially on the same instance, but concurrent use across threads
    is not supported (sqlite3 default `check_same_thread=True`). MCP tools
    construct a fresh `Ontology(path)` per call, which is the intended pattern.
    """

    @classmethod
    def create(cls, path: Path) -> Self:
        """Create a new empty ontology database. Returns an unopened instance."""
        assert_within_workspace(path)
        if path.exists():
            raise OntologyExistsError(path)
        conn = sqlite3.connect(str(path), autocommit=True)
        try:
            _apply_pragmas(conn)
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO metadata (id, data) VALUES (1, ?)",
                (Metadata(prefixes={}, schema_version=CURRENT_SCHEMA_VERSION).model_dump_json(),),
            )
        finally:
            conn.close()
        return cls(path)

    # A: when do we ever supply a session_id?
    def __init__(self, path: Path, *, session_id: str | None = None):
        """Reference an existing ontology. Raises OntologyNotFoundError if missing."""
        assert_within_workspace(path)
        if not path.exists():
            raise OntologyNotFoundError(path)
        self._path = path
        self._session_id = session_id or uuid.uuid4().hex
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        # A: why do we need a StoreNotOpenError? this is an actual bug, never usefully surfaced to MCP user?
        """Active connection. Internal to ontoloom.store.*; MCP tools must not access this directly."""
        if self._conn is None:
            msg = "Store is not open. Use `with Ontology(path) as ont:`."
            raise StoreNotOpenError(msg)
        return self._conn

    @property
    def session_id(self) -> str:
        return self._session_id

    def __enter__(self) -> Self:
        conn = sqlite3.connect(str(self._path), autocommit=True)
        try:
            _apply_pragmas(conn)
            conn.autocommit = False
            _validate_schema(conn)  # A: should only do that once on open ontology, no?
        except Exception:
            conn.close()
            raise
        self._conn = conn
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
