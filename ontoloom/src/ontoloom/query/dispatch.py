"""Public `run()` — verifies selection-scope constraint refs, then delegates to `_run`.

`selection` / `within` fields on a query are the query's own responsibility:
each `_run` calls `get_*_selection` upfront on any such ref so a missing
selection surfaces as `SelectionNotFoundError` instead of an empty result.
"""

from ontoloom.connection import Session
from ontoloom.query.base import Query
from ontoloom.query.constraints import InAxiomSelection, InEntitySelection
from ontoloom.selections.store import axiom_selection_exists, entity_selection_exists
from ontoloom.selections.types import SelectionName, SelectionNotFoundError


def resolve_within(s: Session, name: SelectionName) -> InAxiomSelection | InEntitySelection:
    """Resolve a bare selection name to its kind-scoped constraint by table lookup.

    Unambiguous under the cross-kind uniqueness guard: a name lives in at most
    one table.

    Raises:
        SelectionNotFoundError: name is absent from both tables.
    """
    if axiom_selection_exists(s, name):
        return InAxiomSelection(name=name)

    if entity_selection_exists(s, name):
        return InEntitySelection(name=name)

    raise SelectionNotFoundError(name)


def _verify_in_selection_refs[T](s: Session, q: Query[T]) -> None:
    """Fail loud on a typoed/nonexistent selection-scope constraint.

    Without this, an `InAxiomSelection`/`InEntitySelection` over a nonexistent
    name silently yields an empty result via the pure-SQL EXISTS filter — a
    debugging trap.
    """
    constraints = getattr(q, "constraints", None)
    if constraints is None:
        return

    for c in constraints:
        match c:
            case InAxiomSelection(name=name):
                if not axiom_selection_exists(s, name):
                    raise SelectionNotFoundError(name)
            case InEntitySelection(name=name):
                if not entity_selection_exists(s, name):
                    raise SelectionNotFoundError(name)
            case _:
                continue


def run[T](s: Session, q: Query[T]) -> T:
    _verify_in_selection_refs(s, q)
    return q._run(s)
