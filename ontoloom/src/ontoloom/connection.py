import importlib.resources
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

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


def assert_within_workspace(path: Path):
    if WORKSPACE_ROOT is None:
        return
    if not path.resolve().is_relative_to(WORKSPACE_ROOT):
        msg = f"Path {path!s} is outside the configured workspace ({WORKSPACE_ROOT})."
        raise BadRequestError(msg)


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


def escape_like(value: str):
    """Escape SQL LIKE metacharacters (`\\`, `%`, `_`) so a parameter is matched literally.
    Use with `LIKE ? ESCAPE '\\'`.
    """
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def _apply_pragmas(conn: sqlite3.Connection):
    conn.executescript(_PRAGMAS)


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


@dataclass(frozen=True, slots=True)
class Ontology:
    """Reference to an ontology file. A value type — has a path, no resources."""

    path: Path

    @classmethod
    def create(cls, path: Path):
        """Create a new empty ontology database. Returns a reference to it."""
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
        return cls(path=path)

    def __post_init__(self):
        assert_within_workspace(self.path)

        if not self.path.exists():
            raise OntologyNotFoundError(self.path)


@dataclass(frozen=True, slots=True)
class Session:
    """Active session. Returned by atomic and dry_run."""

    ontology: Ontology
    conn: sqlite3.Connection
    session_id: str
    is_dry_run: bool
