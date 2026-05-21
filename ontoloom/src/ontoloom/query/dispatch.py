"""Public `run()` — verifies `InSelection` constraint refs, then delegates to `_run`.

`selection` / `within` fields on a query are the query's own responsibility:
each `_run` calls `get_selection` upfront on any such ref so a missing
selection surfaces as `SelectionNotFoundError` instead of an empty result.
"""

from ontoloom.connection import Session
from ontoloom.query.base import Query
from ontoloom.query.constraints import InSelection
from ontoloom.selections.persistence import selection_exists
from ontoloom.selections.types import SelectionNotFoundError


def _verify_in_selection_refs[T](s: Session, q: Query[T]) -> None:
    """Fail loud on a typoed/nonexistent `InSelection` constraint ref.

    Without this, an `InSelection(ref=...)` over a nonexistent name silently
    yields an empty result via the pure-SQL EXISTS filter — a debugging trap.
    """
    constraints = getattr(q, "constraints", None)
    if constraints is None:
        return

    for c in constraints:
        if not isinstance(c, InSelection):
            continue

        if not selection_exists(s, c.ref.bare, c.ref.kind):
            raise SelectionNotFoundError(c.ref.bare)


def run[T](s: Session, q: Query[T]) -> T:
    _verify_in_selection_refs(s, q)
    return q._run(s)
