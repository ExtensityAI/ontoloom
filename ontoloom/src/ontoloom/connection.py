import importlib.resources
import os
import sqlite3
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ontoloom.errors import OntoloomError
from ontoloom.models import FrozenModel

_SQL = importlib.resources.files("ontoloom").joinpath("sql")
_SCHEMA = _SQL.joinpath("schema.sql").read_text()
_PRAGMAS = _SQL.joinpath("pragmas.sql").read_text()

CURRENT_SCHEMA_VERSION = 3


# Optional sandbox root for agent-supplied paths. Set `ONTOLOOM_WORKSPACE_ROOT`
# to confine `Ontology(...)` and `export_to_jsonl`. Unset (default)
# means unrestricted, preserving single-user behavior.
_env = os.environ.get("ONTOLOOM_WORKSPACE_ROOT")
WORKSPACE_ROOT = Path(_env).resolve() if _env else None


def assert_within_workspace(path: Path):
    if WORKSPACE_ROOT is None:
        return
    if not path.resolve().is_relative_to(WORKSPACE_ROOT):
        msg = f"Path {path!s} is outside the configured workspace ({WORKSPACE_ROOT})."
        raise PermissionError(msg)


class Metadata(FrozenModel):
    """Typed shape of the singleton row in the `metadata` table."""

    prefixes: dict[str, str]
    schema_version: int


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
    try:
        row = conn.execute("SELECT data FROM metadata WHERE id = 1").fetchone()
    except sqlite3.OperationalError as e:
        msg = f"Not an ontoloom database: {e}"
        raise OntologySchemaError(msg) from e

    if row is None:
        msg = "Not an ontoloom database: metadata row missing"
        raise OntologySchemaError(msg)

    metadata = Metadata.model_validate_json(row[0])

    if metadata.schema_version != CURRENT_SCHEMA_VERSION:
        msg = (
            f"Schema version mismatch: "
            f"expected {CURRENT_SCHEMA_VERSION}, got {metadata.schema_version!r}"
        )
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
        if not path.parent.exists():
            msg = f"Parent directory {str(path.parent)!r} does not exist."
            raise FileNotFoundError(msg)
        try:
            conn = sqlite3.connect(str(path), autocommit=True)
        except sqlite3.OperationalError as e:
            msg = f"Cannot open database at {str(path)!r}: {e}"
            raise OntoloomError(msg) from e
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
    """Active transactional session. Returned by `session()`."""

    ontology: Ontology
    conn: sqlite3.Connection

    def commit(self):
        self.conn.execute("COMMIT")

    def rollback(self):
        self.conn.execute("ROLLBACK")


@contextmanager
def session(ont: Ontology) -> Iterator[Session]:
    """Open a transactional session against the ontology.

    The caller must end the session with `s.commit()` or `s.rollback()`.
    Exceptions inside the `with` block roll back automatically and propagate.
    Exiting without committing or rolling back emits a `RuntimeWarning` and
    rolls back; the project's `filterwarnings = ["error"]` pytest config
    promotes this to a hard test failure.
    """
    try:
        raw = sqlite3.connect(str(ont.path), autocommit=True)
    except sqlite3.OperationalError as e:
        msg = f"Cannot open database at {str(ont.path)!r}: {e}"
        raise OntoloomError(msg) from e
    try:
        try:
            _apply_pragmas(raw)
        except sqlite3.DatabaseError as e:
            msg = f"Cannot read database at {str(ont.path)!r}: {e}"
            raise OntoloomError(msg) from e
        _validate_schema(raw)
        raw.execute("BEGIN")
        s = Session(ontology=ont, conn=raw)
        try:
            yield s
        except:
            if raw.in_transaction:
                raw.execute("ROLLBACK")
            raise
        else:
            if raw.in_transaction:
                warnings.warn(
                    "session exited without commit() or rollback() — rolling back",
                    RuntimeWarning,
                    stacklevel=2,
                )
                raw.execute("ROLLBACK")
    finally:
        raw.close()
