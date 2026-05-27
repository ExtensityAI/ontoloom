"""Parametrized pagination-validator tests across all `HasPagination` query classes."""

from collections.abc import Callable

import pytest
from ontoloom.query.base import Query
from ontoloom.query.list_axioms import ListAxioms
from ontoloom.query.list_entities import ListEntities
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.read_entity_selection import ReadEntitySelection
from ontoloom.selections.types import SelectionName


def _list_entities(**kw: object) -> Query[object]:
    return ListEntities(constraints=(), **kw)  # pyright: ignore[reportArgumentType]


def _list_axioms(**kw: object) -> Query[object]:
    return ListAxioms(constraints=(), **kw)  # pyright: ignore[reportArgumentType]


def _read_axiom_selection(**kw: object) -> Query[object]:
    return ReadAxiomSelection(selection=SelectionName("foo"), **kw)  # pyright: ignore[reportArgumentType]


def _read_entity_selection(**kw: object) -> Query[object]:
    return ReadEntitySelection(selection=SelectionName("foo"), **kw)  # pyright: ignore[reportArgumentType]


_FACTORIES: tuple[Callable[..., Query[object]], ...] = (
    _list_entities,
    _list_axioms,
    _read_axiom_selection,
    _read_entity_selection,
)


@pytest.mark.parametrize("make_query", _FACTORIES, ids=lambda f: f.__name__.lstrip("_"))
def test_rejects_negative_offset(make_query: Callable[..., Query[object]]):
    with pytest.raises(ValueError, match="offset must be >= 0"):
        make_query(offset=-1)


@pytest.mark.parametrize("make_query", _FACTORIES, ids=lambda f: f.__name__.lstrip("_"))
def test_rejects_negative_limit(make_query: Callable[..., Query[object]]):
    with pytest.raises(ValueError, match="limit must be >= 0 if set"):
        make_query(limit=-1)


@pytest.mark.parametrize("make_query", _FACTORIES, ids=lambda f: f.__name__.lstrip("_"))
def test_rejects_offset_without_limit(make_query: Callable[..., Query[object]]):
    with pytest.raises(ValueError, match="offset > 0 requires limit to be set"):
        make_query(offset=5, limit=None)


@pytest.mark.parametrize("make_query", _FACTORIES, ids=lambda f: f.__name__.lstrip("_"))
def test_accepts_zero_offset_without_limit(make_query: Callable[..., Query[object]]):
    q = make_query()
    assert q.offset == 0  # pyright: ignore[reportAttributeAccessIssue]
    assert q.limit is None  # pyright: ignore[reportAttributeAccessIssue]
