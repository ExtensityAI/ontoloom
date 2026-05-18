"""Public `run()` — verifies selection refs, then delegates to the query's `_run` method."""

from ontoloom.connection import Session
from ontoloom.query.base import Query
from ontoloom.query.constraints import InSelection
from ontoloom.selections.types import SelectionNotFoundError, SelectionRef


def _collect_selection_refs[T](q: Query[T]) -> list[SelectionRef]:
    refs: list[SelectionRef] = []

    constraints = getattr(q, "constraints", None)
    if constraints is not None:
        refs.extend(c.ref for c in constraints if isinstance(c, InSelection))

    selection = getattr(q, "selection", None)
    if selection is not None:
        refs.append(selection)

    within = getattr(q, "within", None)
    if within is not None:
        refs.append(within)

    return refs


def _verify_selection_refs[T](s: Session, q: Query[T]):
    """Fail loud on a typoed/nonexistent selection ref before dispatch.

    Without this, an `InSelection(ref=...)` over a nonexistent name silently
    yields an empty result — a silent debugging trap.
    """
    for ref in _collect_selection_refs(q):
        row = s.conn.execute(
            "SELECT 1 FROM selections WHERE name = ? AND kind = ?",
            (ref.bare, ref.kind),
        ).fetchone()

        if row is None:
            raise SelectionNotFoundError(ref.bare)


def run[T](s: Session, q: Query[T]) -> T:
    _verify_selection_refs(s, q)
    return q._run(s)
