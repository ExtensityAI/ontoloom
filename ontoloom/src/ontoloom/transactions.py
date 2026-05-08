import sqlite3
import uuid
import warnings
from collections.abc import Iterator
from contextlib import contextmanager

from ontoloom.connection import Ontology, Session, _apply_pragmas, _validate_schema


@contextmanager
def session(ont: Ontology) -> Iterator[Session]:
    """Open a transactional session against the ontology.

    The caller must end the session with `s.commit()` or `s.rollback()`.
    Exceptions inside the `with` block roll back automatically and propagate.
    Exiting without committing or rolling back emits a `RuntimeWarning` and
    rolls back; the project's `filterwarnings = ["error"]` pytest config
    promotes this to a hard test failure.
    """
    raw = sqlite3.connect(str(ont.path), autocommit=True)
    try:
        _apply_pragmas(raw)
        _validate_schema(raw)
        raw.execute("BEGIN")
        s = Session(ontology=ont, conn=raw, session_id=uuid.uuid4().hex)
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
