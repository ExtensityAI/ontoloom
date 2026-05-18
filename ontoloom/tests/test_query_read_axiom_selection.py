"""Tests for the ReadAxiomSelection query."""

import pytest
from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import HashedAxiom
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import (
    AxiomSelectionName,
    SelectionKind,
    SelectionNotFoundError,
    ShowFilter,
)
from pydantic import ValidationError


def _ref(name: str) -> AxiomSelectionName:
    return AxiomSelectionName(f"axioms:{name}")


# -- field validator: wrong kind --


def test_field_validator_rejects_entity_kind():
    with pytest.raises(ValidationError):
        ReadAxiomSelection(selection="entities:foo")  # pyright: ignore[reportArgumentType]


def test_field_validator_accepts_axiom_kind():
    q = ReadAxiomSelection(selection=_ref("foo"))
    assert q.selection.kind == SelectionKind.AXIOMS


# -- render snapshots --


def test_render_default_show_all_no_pagination():
    compiled = (ReadAxiomSelection(selection=_ref("sel"))).render()
    assert compiled.sql == (
        "SELECT si.item, json(a.data) "
        "FROM selection_items si LEFT JOIN axioms a ON a.hash = si.item "
        "WHERE si.selection_name = ? "
        "ORDER BY si.rowid"
    )
    assert compiled.params == ("sel",)


def test_render_show_present():
    compiled = (ReadAxiomSelection(selection=_ref("sel"), show=ShowFilter.PRESENT)).render()
    assert "AND a.id IS NOT NULL" in compiled.sql
    assert "AND a.id IS NULL" not in compiled.sql


def test_render_show_missing():
    compiled = (ReadAxiomSelection(selection=_ref("sel"), show=ShowFilter.MISSING)).render()
    assert "AND a.id IS NULL" in compiled.sql
    assert "AND a.id IS NOT NULL" not in compiled.sql


def test_render_limit_and_offset():
    compiled = (ReadAxiomSelection(selection=_ref("sel"), limit=5, offset=2)).render()
    assert compiled.sql.endswith("ORDER BY si.rowid LIMIT ? OFFSET ?")
    assert compiled.params == ("sel", 5, 2)


def test_render_limit_only():
    compiled = (ReadAxiomSelection(selection=_ref("sel"), limit=10)).render()
    assert compiled.sql.endswith("ORDER BY si.rowid LIMIT ?")
    assert compiled.params == ("sel", 10)


# -- _run integration --


def test_run_missing_selection_raises(s):
    with pytest.raises(SelectionNotFoundError):
        (ReadAxiomSelection(selection=_ref("nope")))._run(s)


def test_run_basic_present_and_missing(s):
    ax = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    add_axioms(s, [ax])
    real_hash = HashedAxiom.of(ax).hash
    fake_hash = "d" * 64

    upsert_selection(s, "sel", SelectionKind.AXIOMS, [real_hash, fake_hash], "test")

    page = (ReadAxiomSelection(selection=_ref("sel")))._run(s)
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

    page = (ReadAxiomSelection(selection=_ref("sel"), show=ShowFilter.PRESENT))._run(s)
    assert page.total_filtered == 1
    assert len(page.items) == 1
    assert all(not item.missing for item in page.items)


def test_run_show_missing_only(s):
    ax = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    add_axioms(s, [ax])
    real_hash = HashedAxiom.of(ax).hash
    fake_hash = "d" * 64
    upsert_selection(s, "sel", SelectionKind.AXIOMS, [real_hash, fake_hash], "test")

    page = (ReadAxiomSelection(selection=_ref("sel"), show=ShowFilter.MISSING))._run(s)
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

    full = (ReadAxiomSelection(selection=_ref("sel")))._run(s)
    full_hashes = [i.hash for i in full.items]

    page1 = (ReadAxiomSelection(selection=_ref("sel"), limit=2))._run(s)
    page2 = (ReadAxiomSelection(selection=_ref("sel"), limit=2, offset=2))._run(s)
    paged = [i.hash for i in page1.items] + [i.hash for i in page2.items]
    assert paged == full_hashes


def test_run_empty_selection(s):
    upsert_selection(s, "empty", SelectionKind.AXIOMS, [], "test")
    page = (ReadAxiomSelection(selection=_ref("empty")))._run(s)
    assert page.items == ()
    assert page.total_filtered == 0
    assert page.present == 0
    assert page.missing == 0
