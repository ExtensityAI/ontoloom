"""Read-only selection-metadata lookup; sits below `selections.store` to break cycles."""

from ontoloom.connection import Session
from ontoloom.selections.types import (
    SelectionContentHash,
    SelectionKind,
    SelectionMeta,
    SelectionName,
    SelectionNotFoundError,
)


def get_selection_meta(s: Session, name: SelectionName) -> SelectionMeta:
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
