"""Tests for the ReadAxiomSelection / ReadEntitySelection queries.

Parallel tests for the two read-selection queries are parametrized over
`(query_class, ref_factory, meta_class, seed_present_missing)`. Tests whose
assertions diverge meaningfully (labels, punning) stay standalone below.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import pytest
from ontoloom.axioms.mutations import add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.owl.axioms import AnnotationAssertion, Declaration, SubClassOf
from ontoloom.owl.iri import IRI, RDFS_LABEL
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.query.dispatch import execute
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.read_entity_selection import ReadEntitySelection
from ontoloom.selections.store import upsert_axiom_selection, upsert_entity_selection
from ontoloom.selections.types import (
    AxiomSelection,
    EntitySelection,
    SelectionKind,
    SelectionKindMismatchError,
    SelectionName,
    SelectionNotFoundError,
    ShowFilter,
)
from pydantic import ValidationError

SEL = SelectionName("sel")


def _seed_axioms_present_missing(s: Any, name: SelectionName) -> None:
    ax = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    add_axioms(s, [ax])
    real_hash = HashedAxiom.of(ax).hash
    fake_hash = "d" * 64
    upsert_axiom_selection(s, name, [real_hash, fake_hash], "test")


def _seed_entities_present_missing(s: Any, name: SelectionName) -> None:
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    upsert_entity_selection(s, name, ["ex:Dog", "ex:Ghost"], "test")


def _seed_axioms_for_pagination(s: Any, name: SelectionName) -> None:
    axs = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
    ]
    add_axioms(s, axs)
    hashes = [HashedAxiom.of(a).hash for a in axs]
    upsert_axiom_selection(s, name, hashes, "test")


def _seed_entities_for_pagination(s: Any, name: SelectionName) -> None:
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
        ],
    )
    upsert_entity_selection(
        s,
        name,
        ["ex:Zebra", "ex:Antelope", "ex:Mongoose"],
        "test",
    )


def _seed_empty_axioms(s: Any, name: SelectionName) -> None:
    upsert_axiom_selection(s, name, [], "test")


def _seed_empty_entities(s: Any, name: SelectionName) -> None:
    upsert_entity_selection(s, name, [], "test")


@dataclass(frozen=True, slots=True)
class _ReadParams:
    query_class: type
    ref_factory: Callable[[str], Any]
    meta_class: type
    seed_pm: Callable[..., None]
    seed_pag: Callable[..., None]
    seed_empty: Callable[..., None]


_AXIOM_PARAMS = _ReadParams(
    query_class=ReadAxiomSelection,
    ref_factory=SelectionName,
    meta_class=AxiomSelection,
    seed_pm=_seed_axioms_present_missing,
    seed_pag=_seed_axioms_for_pagination,
    seed_empty=_seed_empty_axioms,
)
_ENTITY_PARAMS = _ReadParams(
    query_class=ReadEntitySelection,
    ref_factory=SelectionName,
    meta_class=EntitySelection,
    seed_pm=_seed_entities_present_missing,
    seed_pag=_seed_entities_for_pagination,
    seed_empty=_seed_empty_entities,
)

PARAMS = pytest.mark.parametrize("p", [_AXIOM_PARAMS, _ENTITY_PARAMS], ids=["axiom", "entity"])


# -- field validator --


@PARAMS
def test_field_validator_rejects_invalid_name(p: _ReadParams):
    with pytest.raises(ValidationError):
        p.query_class(selection="not a valid name")


@PARAMS
def test_field_validator_accepts_valid_name(p: _ReadParams):
    q = p.query_class(selection=p.ref_factory("foo"))
    assert q.selection == p.ref_factory("foo")


# -- _run integration: shared behavior --


@PARAMS
def test_run_missing_selection_raises(s, p: _ReadParams):
    with pytest.raises(SelectionNotFoundError):
        execute(s, p.query_class(selection=p.ref_factory("nope")))


@PARAMS
def test_run_basic_present_and_missing(s, p: _ReadParams):
    p.seed_pm(s, "sel")
    page = execute(s, p.query_class(selection=p.ref_factory("sel")))
    assert isinstance(page.meta, p.meta_class)
    assert page.meta.size == 2
    assert page.total_filtered == 2
    assert page.present == 1
    assert page.missing == 1
    assert page.show == ShowFilter.ALL
    assert len(page.items) == 2


@PARAMS
def test_run_show_present_only(s, p: _ReadParams):
    p.seed_pm(s, "sel")
    page = execute(s, p.query_class(selection=p.ref_factory("sel"), show=ShowFilter.PRESENT))
    assert page.total_filtered == 1
    assert len(page.items) == 1


@PARAMS
def test_run_show_missing_only(s, p: _ReadParams):
    p.seed_pm(s, "sel")
    page = execute(s, p.query_class(selection=p.ref_factory("sel"), show=ShowFilter.MISSING))
    assert page.total_filtered == 1
    assert len(page.items) == 1


def _item_key(item: Any) -> str:
    # axiom items expose `.hash`, entity items expose `.iri`
    return getattr(item, "hash", None) or str(item.iri)


@PARAMS
def test_run_pagination_is_consistent(s, p: _ReadParams):
    """Concatenated paginated reads equal the unpaginated read.

    Specific order is per-query contract (`ReadAxiomSelection` = insertion
    order, `ReadEntitySelection` = lex on IRI); covered by the dedicated
    order tests below.
    """
    p.seed_pag(s, "sel")
    full = execute(s, p.query_class(selection=p.ref_factory("sel")))
    full_keys: Sequence[str] = [_item_key(i) for i in full.items]

    page1 = execute(s, p.query_class(selection=p.ref_factory("sel"), limit=2))
    page2 = execute(s, p.query_class(selection=p.ref_factory("sel"), limit=2, offset=2))
    paged = [_item_key(i) for i in page1.items] + [_item_key(i) for i in page2.items]
    assert paged == list(full_keys)


def test_axiom_run_returns_items_in_insertion_order(s):
    axs = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
    ]
    add_axioms(s, axs)
    hashes = [HashedAxiom.of(a).hash for a in axs]
    upsert_axiom_selection(s, SEL, hashes, "test")

    page = execute(s, ReadAxiomSelection(selection=SelectionName("sel")))
    assert [item.hash for item in page.items] == hashes


def test_axiom_read_does_not_see_entity_selection_with_same_name(s):
    upsert_entity_selection(s, SelectionName("foo"), ["ex:Dog"], "test")
    with pytest.raises(SelectionKindMismatchError) as exc_info:
        execute(s, ReadAxiomSelection(selection=SelectionName("foo")))
    assert exc_info.value.actual == SelectionKind.ENTITIES
    assert exc_info.value.expected == SelectionKind.AXIOMS


def test_entity_read_does_not_see_axiom_selection_with_same_name(s):
    upsert_axiom_selection(s, SelectionName("foo"), ["a" * 64], "test")
    with pytest.raises(SelectionKindMismatchError) as exc_info:
        execute(s, ReadEntitySelection(selection=SelectionName("foo")))
    assert exc_info.value.actual == SelectionKind.AXIOMS
    assert exc_info.value.expected == SelectionKind.ENTITIES


def test_entity_run_returns_items_in_lex_order(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
        ],
    )
    upsert_entity_selection(
        s,
        SEL,
        ["ex:Zebra", "ex:Antelope", "ex:Mongoose"],
        "test",
    )

    page = execute(s, ReadEntitySelection(selection=SelectionName("sel")))
    assert [str(item.iri) for item in page.items] == ["ex:Antelope", "ex:Mongoose", "ex:Zebra"]


@PARAMS
def test_run_empty_selection(s, p: _ReadParams):
    p.seed_empty(s, SelectionName("empty"))
    page = execute(s, p.query_class(selection=p.ref_factory("empty")))
    assert page.items == ()
    assert page.total_filtered == 0
    assert page.present == 0
    assert page.missing == 0


# -- entity-only behavioral tests --


def test_entity_run_present_and_missing_classified(s):
    _seed_entities_present_missing(s, SEL)
    page = execute(s, ReadEntitySelection(selection=SelectionName("sel")))
    by_iri = {item.iri: item for item in page.items}
    assert by_iri[IRI("ex:Dog")].present is True
    assert by_iri[IRI("ex:Dog")].roles == frozenset({EntityType.CLASS})
    assert by_iri[IRI("ex:Ghost")].present is False
    assert by_iri[IRI("ex:Ghost")].roles == frozenset()


def test_entity_run_show_present_returns_only_dog(s):
    _seed_entities_present_missing(s, SEL)
    page = execute(s, ReadEntitySelection(selection=SelectionName("sel"), show=ShowFilter.PRESENT))
    assert page.items[0].iri == IRI("ex:Dog")
    assert page.items[0].present is True


def test_entity_run_show_missing_returns_only_ghost(s):
    _seed_entities_present_missing(s, SEL)
    page = execute(s, ReadEntitySelection(selection=SelectionName("sel"), show=ShowFilter.MISSING))
    assert page.items[0].iri == IRI("ex:Ghost")
    assert page.items[0].present is False


def test_entity_run_labels_populated_for_present_entities(s):
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
    upsert_entity_selection(s, SEL, ["ex:Dog"], "test")
    page = execute(s, ReadEntitySelection(selection=SelectionName("sel")))
    assert page.items[0].label == "Dog"


def test_entity_run_punned_entity_present_missing_invariant(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:X")),
            Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI("ex:X")),
        ],
    )
    upsert_entity_selection(s, SEL, ["ex:X", "ex:Ghost"], "test")
    page = execute(s, ReadEntitySelection(selection=SelectionName("sel")))
    assert page.present + page.missing == page.meta.size
    assert page.present == 1
    assert page.missing == 1


def test_entity_run_punned_entity_reports_all_roles(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Pun")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:Pun")),
        ],
    )
    upsert_entity_selection(s, SEL, ["ex:Pun"], "test")
    page = execute(s, ReadEntitySelection(selection=SelectionName("sel")))
    item = next(i for i in page.items if i.iri == IRI("ex:Pun"))
    assert item.roles == frozenset({EntityType.CLASS, EntityType.OBJECT_PROPERTY})


# -- axiom-only behavioral assertions --


def test_axiom_run_show_present_items_not_missing(s):
    _seed_axioms_present_missing(s, SEL)
    page = execute(s, ReadAxiomSelection(selection=SelectionName("sel"), show=ShowFilter.PRESENT))
    assert all(not item.missing for item in page.items)


def test_axiom_run_show_missing_items_all_missing(s):
    _seed_axioms_present_missing(s, SEL)
    page = execute(s, ReadAxiomSelection(selection=SelectionName("sel"), show=ShowFilter.MISSING))
    assert all(item.missing for item in page.items)


def test_axiom_run_basic_meta_name(s):
    _seed_axioms_present_missing(s, SEL)
    page = execute(s, ReadAxiomSelection(selection=SelectionName("sel")))
    assert page.meta.name == "sel"
