"""Tests for the ReadEntitySelection query."""

import pytest
from ontoloom.axioms.store import add_axioms
from ontoloom.owl.axioms import AnnotationAssertion, Declaration
from ontoloom.owl.iri import IRI, RDFS_LABEL
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.query.read_entity_selection import ReadEntitySelection, _run, render
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import (
    SelectionKind,
    SelectionKindError,
    SelectionNotFoundError,
    ShowFilter,
)


def _ref(name: str, kind: SelectionKind = SelectionKind.ENTITIES) -> ResolvedSelection:
    return ResolvedSelection(kind=kind, bare_name=name)


# -- field validator: wrong kind --


def test_field_validator_rejects_axiom_kind():
    with pytest.raises(SelectionKindError):
        ReadEntitySelection(selection=_ref("foo", SelectionKind.AXIOMS))


def test_field_validator_accepts_entity_kind():
    q = ReadEntitySelection(selection=_ref("foo", SelectionKind.ENTITIES))
    assert q.selection.kind == SelectionKind.ENTITIES


# -- pagination validators --


def test_validator_rejects_negative_offset():
    with pytest.raises(ValueError, match="offset must be >= 0"):
        ReadEntitySelection(selection=_ref("foo"), offset=-1)


def test_validator_rejects_negative_limit():
    with pytest.raises(ValueError, match="limit must be >= 0 if set"):
        ReadEntitySelection(selection=_ref("foo"), limit=-1)


def test_validator_rejects_offset_without_limit():
    with pytest.raises(ValueError, match="offset > 0 requires limit to be set"):
        ReadEntitySelection(selection=_ref("foo"), offset=3, limit=None)


# -- render snapshots --


def test_render_default_show_all_no_pagination():
    compiled = render(ReadEntitySelection(selection=_ref("sel")))
    assert compiled.sql == (
        "SELECT si.item, "
        "EXISTS (SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item) AS is_present "
        "FROM selection_items si "
        "WHERE si.selection_name = ? "
        "ORDER BY si.rowid"
    )
    assert compiled.params == ("sel",)


def test_render_show_present_uses_exists():
    compiled = render(ReadEntitySelection(selection=_ref("sel"), show=ShowFilter.PRESENT))
    assert " AND EXISTS (SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item)" in (
        compiled.sql
    )
    assert "NOT EXISTS" not in compiled.sql


def test_render_show_missing_uses_not_exists():
    compiled = render(ReadEntitySelection(selection=_ref("sel"), show=ShowFilter.MISSING))
    assert " AND NOT EXISTS (SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item)" in (
        compiled.sql
    )


def test_render_limit_and_offset():
    compiled = render(ReadEntitySelection(selection=_ref("sel"), limit=5, offset=2))
    assert compiled.sql.endswith("ORDER BY si.rowid LIMIT ? OFFSET ?")
    assert compiled.params == ("sel", 5, 2)


# -- _run integration --


def test_run_missing_selection_raises(s):
    with pytest.raises(SelectionNotFoundError):
        _run(s, ReadEntitySelection(selection=_ref("nope")))


def test_run_present_and_missing_classified(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    upsert_selection(s, "sel", SelectionKind.ENTITIES, ["ex:Dog", "ex:Ghost"], "test")

    page = _run(s, ReadEntitySelection(selection=_ref("sel")))
    assert page.meta.kind == SelectionKind.ENTITIES
    assert page.meta.size == 2
    assert page.total_filtered == 2
    assert page.present == 1
    assert page.missing == 1

    by_iri = {item.iri: item for item in page.items}
    assert by_iri[IRI("ex:Dog")].present is True
    assert by_iri[IRI("ex:Dog")].role == EntityType.CLASS
    assert by_iri[IRI("ex:Ghost")].present is False
    assert by_iri[IRI("ex:Ghost")].role is None


def test_run_show_present(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    upsert_selection(s, "sel", SelectionKind.ENTITIES, ["ex:Dog", "ex:Ghost"], "test")

    page = _run(s, ReadEntitySelection(selection=_ref("sel"), show=ShowFilter.PRESENT))
    assert page.total_filtered == 1
    assert len(page.items) == 1
    assert page.items[0].iri == IRI("ex:Dog")
    assert page.items[0].present is True


def test_run_show_missing(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    upsert_selection(s, "sel", SelectionKind.ENTITIES, ["ex:Dog", "ex:Ghost"], "test")

    page = _run(s, ReadEntitySelection(selection=_ref("sel"), show=ShowFilter.MISSING))
    assert page.total_filtered == 1
    assert len(page.items) == 1
    assert page.items[0].iri == IRI("ex:Ghost")
    assert page.items[0].present is False


def test_run_labels_populated_for_present_entities(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            AnnotationAssertion(
                property=RDFS_LABEL,
                subject=IRI("ex:Dog"),
                value=LangLiteral(value="Dog"),
            ),
        ],
    )
    upsert_selection(s, "sel", SelectionKind.ENTITIES, ["ex:Dog"], "test")

    page = _run(s, ReadEntitySelection(selection=_ref("sel")))
    assert len(page.items) == 1
    assert page.items[0].label == "Dog"


def test_run_pagination_in_insertion_order(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
        ],
    )
    upsert_selection(
        s, "sel", SelectionKind.ENTITIES, ["ex:Zebra", "ex:Antelope", "ex:Mongoose"], "test"
    )

    full = _run(s, ReadEntitySelection(selection=_ref("sel")))
    iris_full = [i.iri for i in full.items]

    page1 = _run(s, ReadEntitySelection(selection=_ref("sel"), limit=2))
    page2 = _run(s, ReadEntitySelection(selection=_ref("sel"), limit=2, offset=2))
    iris_paged = [i.iri for i in page1.items] + [i.iri for i in page2.items]

    assert iris_paged == iris_full


def test_run_empty_selection(s):
    upsert_selection(s, "empty", SelectionKind.ENTITIES, [], "test")
    page = _run(s, ReadEntitySelection(selection=_ref("empty")))
    assert page.items == ()
    assert page.total_filtered == 0
    assert page.present == 0
    assert page.missing == 0


def test_run_punned_entity_present_missing_invariant(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:X")),
            Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI("ex:X")),
        ],
    )
    upsert_selection(s, "sel", SelectionKind.ENTITIES, ["ex:X", "ex:Ghost"], "test")
    page = _run(s, ReadEntitySelection(selection=_ref("sel")))
    assert page.present + page.missing == page.meta.size
    assert page.present == 1
    assert page.missing == 1
