import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from ontoloom.connection import Ontology, Session, _apply_pragmas, _validate_schema


@contextmanager
def _open_session(ont: Ontology, *, is_dry_run: bool) -> Iterator[Session]:
    """Open conn, apply pragmas, validate schema, BEGIN. Always close on exit."""
    raw = sqlite3.connect(str(ont.path), autocommit=True)
    try:
        _apply_pragmas(raw)
        _validate_schema(raw)
        raw.execute("BEGIN")
        yield Session(
            ontology=ont,
            conn=raw,
            session_id=uuid.uuid4().hex,
            is_dry_run=is_dry_run,
        )
    finally:
        raw.close()


@contextmanager
def atomic(ont: Ontology) -> Iterator[Session]:
    with _open_session(ont, is_dry_run=False) as s:
        try:
            yield s
            s.conn.execute("COMMIT")
        except:
            s.conn.execute("ROLLBACK")
            raise


@contextmanager
def dry_run(ont: Ontology) -> Iterator[Session]:
    with _open_session(ont, is_dry_run=True) as s:
        try:
            yield s
        finally:
            s.conn.execute("ROLLBACK")
