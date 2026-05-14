"""Tests for the ReadAxiomSelection query."""

import pytest
from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import HashedAxiom
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.query.read_axiom_selection import ReadAxiomSelection, _run, render
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import (
    SelectionKind,
    SelectionKindError,
    SelectionNotFoundError,
    ShowFilter,
)


def _ref(name: str, kind: SelectionKind = SelectionKind.AXIOMS) -> ResolvedSelection:
    return ResolvedSelection(kind=kind, bare_name=name)


# -- field validator: wrong kind --


def test_field_validator_rejects_entity_kind():
    with pytest.raises(SelectionKindError):
        ReadAxiomSelection(selection=_ref("foo", SelectionKind.ENTITIES))


def test_field_validator_accepts_axiom_kind():
    q = ReadAxiomSelection(selection=_ref("foo", SelectionKind.AXIOMS))
    assert q.selection.kind == SelectionKind.AXIOMS


# -- pagination validators --


def test_validator_rejects_negative_offset():
    with pytest.raises(ValueError, match="offset must be >= 0"):
        ReadAxiomSelection(selection=_ref("foo"), offset=-1)


def test_validator_rejects_negative_limit():
    with pytest.raises(ValueError, match="limit must be >= 0 if set"):
        ReadAxiomSelection(selection=_ref("foo"), limit=-1)


def test_validator_rejects_offset_without_limit():
    with pytest.raises(ValueError, match="offset > 0 requires limit to be set"):
        ReadAxiomSelection(selection=_ref("foo"), offset=3, limit=None)


# -- render snapshots --


def test_render_default_show_all_no_pagination():
    compiled = render(ReadAxiomSelection(selection=_ref("sel")))
    assert compiled.sql == (
        "SELECT si.item, json(a.data) "
        "FROM selection_items si LEFT JOIN axioms a ON a.hash = si.item "
        "WHERE si.selection_name = ? "
        "ORDER BY si.rowid"
    )
    assert compiled.params == ("sel",)


def test_render_show_present():
    compiled = render(ReadAxiomSelection(selection=_ref("sel"), show=ShowFilter.PRESENT))
    assert "AND a.id IS NOT NULL" in compiled.sql
    assert "AND a.id IS NULL" not in compiled.sql


def test_render_show_missing():
    compiled = render(ReadAxiomSelection(selection=_ref("sel"), show=ShowFilter.MISSING))
    assert "AND a.id IS NULL" in compiled.sql
    assert "AND a.id IS NOT NULL" not in compiled.sql


def test_render_limit_and_offset():
    compiled = render(ReadAxiomSelection(selection=_ref("sel"), limit=5, offset=2))
    assert compiled.sql.endswith("ORDER BY si.rowid LIMIT ? OFFSET ?")
    assert compiled.params == ("sel", 5, 2)


def test_render_limit_only():
    compiled = render(ReadAxiomSelection(selection=_ref("sel"), limit=10))
    assert compiled.sql.endswith("ORDER BY si.rowid LIMIT ?")
    assert compiled.params == ("sel", 10)


# -- _run integration --


def test_run_missing_selection_raises(s):
    with pytest.raises(SelectionNotFoundError):
        _run(s, ReadAxiomSelection(selection=_ref("nope")))


def test_run_basic_present_and_missing(s):
    ax = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    add_axioms(s, [ax])
    real_hash = HashedAxiom.of(ax).hash
    fake_hash = "d" * 64

    upsert_selection(s, "sel", SelectionKind.AXIOMS, [real_hash, fake_hash], "test")

    page = _run(s, ReadAxiomSelection(selection=_ref("sel")))
    assert page.meta.name == "sel"
    assert page.meta.kind == SelectionKind.AXIOMS
    assert page.meta.size == 2
    assert len(page.items) == 2
    assert page.total_filtered == 2
    assert page.present == 1
    assert page.missing == 1
    assert page.show == ShowFilter.ALL


def test_run_show_present_only(s):
    ax = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    add_axioms(s, [ax])
    real_hash = HashedAxiom.of(ax).hash
    fake_hash = "d" * 64
    upsert_selection(s, "sel", SelectionKind.AXIOMS, [real_hash, fake_hash], "test")

    page = _run(s, ReadAxiomSelection(selection=_ref("sel"), show=ShowFilter.PRESENT))
    assert page.total_filtered == 1
    assert len(page.items) == 1
    assert all(not item.missing for item in page.items)


def test_run_show_missing_only(s):
    ax = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    add_axioms(s, [ax])
    real_hash = HashedAxiom.of(ax).hash
    fake_hash = "d" * 64
    upsert_selection(s, "sel", SelectionKind.AXIOMS, [real_hash, fake_hash], "test")

    page = _run(s, ReadAxiomSelection(selection=_ref("sel"), show=ShowFilter.MISSING))
    assert page.total_filtered == 1
    assert len(page.items) == 1
    assert all(item.missing for item in page.items)


def test_run_pagination_walks_in_insertion_order(s):
    axs = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
    ]
    add_axioms(s, axs)
    hashes = [HashedAxiom.of(a).hash for a in axs]
    upsert_selection(s, "sel", SelectionKind.AXIOMS, hashes, "test")

    full = _run(s, ReadAxiomSelection(selection=_ref("sel")))
    full_hashes = [i.hash for i in full.items]

    page1 = _run(s, ReadAxiomSelection(selection=_ref("sel"), limit=2))
    page2 = _run(s, ReadAxiomSelection(selection=_ref("sel"), limit=2, offset=2))
    paged = [i.hash for i in page1.items] + [i.hash for i in page2.items]
    assert paged == full_hashes


def test_run_empty_selection(s):
    upsert_selection(s, "empty", SelectionKind.AXIOMS, [], "test")
    page = _run(s, ReadAxiomSelection(selection=_ref("empty")))
    assert page.items == ()
    assert page.total_filtered == 0
    assert page.present == 0
    assert page.missing == 0
