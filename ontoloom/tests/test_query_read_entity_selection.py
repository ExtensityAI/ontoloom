"""Tests for the ReadEntitySelection query."""

import pytest
from ontoloom.axioms.store import add_axioms
from ontoloom.owl.axioms import AnnotationAssertion, Declaration
from ontoloom.owl.iri import IRI, RDFS_LABEL
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.query.read_entity_selection import ReadEntitySelection
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import (
    EntitySelectionName,
    SelectionKind,
    SelectionNotFoundError,
    ShowFilter,
)
from pydantic import ValidationError


def _ref(name: str) -> EntitySelectionName:
    return EntitySelectionName(f"entities:{name}")


# -- field validator: wrong kind --


def test_field_validator_rejects_axiom_kind():
    with pytest.raises(ValidationError):
        ReadEntitySelection(selection="axioms:foo")  # pyright: ignore[reportArgumentType]


def test_field_validator_accepts_entity_kind():
    q = ReadEntitySelection(selection=_ref("foo"))
    assert q.selection.kind == SelectionKind.ENTITIES


# -- render snapshots --


def test_render_default_show_all_no_pagination():
    compiled = (ReadEntitySelection(selection=_ref("sel"))).render()
    assert compiled.sql == (
        "SELECT si.item, "
        "EXISTS (SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item) AS is_present "
        "FROM selection_items si "
        "WHERE si.selection_name = ? "
        "ORDER BY si.item"
    )
    assert compiled.params == ("sel",)


def test_render_show_present_uses_exists():
    compiled = (ReadEntitySelection(selection=_ref("sel"), show=ShowFilter.PRESENT)).render()
    assert " AND EXISTS (SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item)" in (
        compiled.sql
    )
    assert "NOT EXISTS" not in compiled.sql


def test_render_show_missing_uses_not_exists():
    compiled = (ReadEntitySelection(selection=_ref("sel"), show=ShowFilter.MISSING)).render()
    assert " AND NOT EXISTS (SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item)" in (
        compiled.sql
    )


def test_render_limit_and_offset():
    compiled = (ReadEntitySelection(selection=_ref("sel"), limit=5, offset=2)).render()
    assert compiled.sql.endswith("ORDER BY si.item LIMIT ? OFFSET ?")
    assert compiled.params == ("sel", 5, 2)


# -- _run integration --


def test_run_missing_selection_raises(s):
    with pytest.raises(SelectionNotFoundError):
        (ReadEntitySelection(selection=_ref("nope")))._run(s)


def test_run_present_and_missing_classified(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    upsert_selection(s, "sel", SelectionKind.ENTITIES, ["ex:Dog", "ex:Ghost"], "test")

    page = (ReadEntitySelection(selection=_ref("sel")))._run(s)
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

    page = (ReadEntitySelection(selection=_ref("sel"), show=ShowFilter.PRESENT))._run(s)
    assert page.total_filtered == 1
    assert len(page.items) == 1
    assert page.items[0].iri == IRI("ex:Dog")
    assert page.items[0].present is True


def test_run_show_missing(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    upsert_selection(s, "sel", SelectionKind.ENTITIES, ["ex:Dog", "ex:Ghost"], "test")

    page = (ReadEntitySelection(selection=_ref("sel"), show=ShowFilter.MISSING))._run(s)
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

    page = (ReadEntitySelection(selection=_ref("sel")))._run(s)
    assert len(page.items) == 1
    assert page.items[0].label == "Dog"


def test_run_pagination_in_lexicographic_order(s):
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

    full = (ReadEntitySelection(selection=_ref("sel")))._run(s)
    iris_full = [i.iri for i in full.items]
    assert iris_full == [IRI("ex:Antelope"), IRI("ex:Mongoose"), IRI("ex:Zebra")]

    page1 = (ReadEntitySelection(selection=_ref("sel"), limit=2))._run(s)
    page2 = (ReadEntitySelection(selection=_ref("sel"), limit=2, offset=2))._run(s)
    iris_paged = [i.iri for i in page1.items] + [i.iri for i in page2.items]

    assert iris_paged == iris_full


def test_run_empty_selection(s):
    upsert_selection(s, "empty", SelectionKind.ENTITIES, [], "test")
    page = (ReadEntitySelection(selection=_ref("empty")))._run(s)
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
    page = (ReadEntitySelection(selection=_ref("sel")))._run(s)
    assert page.present + page.missing == page.meta.size
    assert page.present == 1
    assert page.missing == 1
