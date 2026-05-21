"""Tests for the ReadAxiomSelection / ReadEntitySelection queries.

Parallel tests for the two read-selection queries are parametrized over
`(query_class, ref_factory, kind, seed_present_missing)`. Tests whose
assertions diverge meaningfully (labels, punning) stay standalone below.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import pytest
from ontoloom.axioms.mutations import add_axioms
from ontoloom.hashing import HashedAxiom
from ontoloom.owl.axioms import AnnotationAssertion, Declaration, SubClassOf
from ontoloom.owl.iri import IRI, RDFS_LABEL
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.query.dispatch import run
from ontoloom.selections.persistence import upsert_selection
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.read_entity_selection import ReadEntitySelection
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
    SelectionKind,
    SelectionKindMismatchError,
    SelectionName,
    SelectionNotFoundError,
    ShowFilter,
)
from pydantic import ValidationError

SEL = SelectionName("sel")


def _axiom_ref(name: str) -> AxiomSelectionName:
    return AxiomSelectionName(f"axioms:{name}")


def _entity_ref(name: str) -> EntitySelectionName:
    return EntitySelectionName(f"entities:{name}")


def _seed_axioms_present_missing(s: Any, name: SelectionName) -> None:
    ax = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    add_axioms(s, [ax])
    real_hash = HashedAxiom.of(ax).hash
    fake_hash = "d" * 64
    upsert_selection(s, name, SelectionKind.AXIOMS, [real_hash, fake_hash], "test")


def _seed_entities_present_missing(s: Any, name: SelectionName) -> None:
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    upsert_selection(s, name, SelectionKind.ENTITIES, ["ex:Dog", "ex:Ghost"], "test")


def _seed_axioms_for_pagination(s: Any, name: SelectionName) -> None:
    axs = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
    ]
    add_axioms(s, axs)
    hashes = [HashedAxiom.of(a).hash for a in axs]
    upsert_selection(s, name, SelectionKind.AXIOMS, hashes, "test")


def _seed_entities_for_pagination(s: Any, name: SelectionName) -> None:
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
        ],
    )
    upsert_selection(
        s,
        name,
        SelectionKind.ENTITIES,
        ["ex:Zebra", "ex:Antelope", "ex:Mongoose"],
        "test",
    )


@dataclass(frozen=True, slots=True)
class _ReadParams:
    query_class: type
    ref_factory: Callable[[str], Any]
    kind: SelectionKind
    wrong_kind_str: str
    seed_pm: Callable[..., None]
    seed_pag: Callable[..., None]


_AXIOM_PARAMS = _ReadParams(
    query_class=ReadAxiomSelection,
    ref_factory=_axiom_ref,
    kind=SelectionKind.AXIOMS,
    wrong_kind_str="entities:foo",
    seed_pm=_seed_axioms_present_missing,
    seed_pag=_seed_axioms_for_pagination,
)
_ENTITY_PARAMS = _ReadParams(
    query_class=ReadEntitySelection,
    ref_factory=_entity_ref,
    kind=SelectionKind.ENTITIES,
    wrong_kind_str="axioms:foo",
    seed_pm=_seed_entities_present_missing,
    seed_pag=_seed_entities_for_pagination,
)

PARAMS = pytest.mark.parametrize("p", [_AXIOM_PARAMS, _ENTITY_PARAMS], ids=["axiom", "entity"])


# -- field validator --


@PARAMS
def test_field_validator_rejects_wrong_kind(p: _ReadParams):
    with pytest.raises(ValidationError):
        p.query_class(selection=p.wrong_kind_str)


@PARAMS
def test_field_validator_accepts_correct_kind(p: _ReadParams):
    q = p.query_class(selection=p.ref_factory("foo"))
    assert q.selection.kind == p.kind


# -- _run integration: shared behavior --


@PARAMS
def test_run_missing_selection_raises(s, p: _ReadParams):
    with pytest.raises(SelectionNotFoundError):
        run(s, p.query_class(selection=p.ref_factory("nope")))


@PARAMS
def test_run_basic_present_and_missing(s, p: _ReadParams):
    p.seed_pm(s, "sel")
    page = run(s, p.query_class(selection=p.ref_factory("sel")))
    assert page.meta.kind == p.kind
    assert page.meta.size == 2
    assert page.total_filtered == 2
    assert page.present == 1
    assert page.missing == 1
    assert page.show == ShowFilter.ALL
    assert len(page.items) == 2


@PARAMS
def test_run_show_present_only(s, p: _ReadParams):
    p.seed_pm(s, "sel")
    page = run(s, p.query_class(selection=p.ref_factory("sel"), show=ShowFilter.PRESENT))
    assert page.total_filtered == 1
    assert len(page.items) == 1


@PARAMS
def test_run_show_missing_only(s, p: _ReadParams):
    p.seed_pm(s, "sel")
    page = run(s, p.query_class(selection=p.ref_factory("sel"), show=ShowFilter.MISSING))
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
    full = run(s, p.query_class(selection=p.ref_factory("sel")))
    full_keys: Sequence[str] = [_item_key(i) for i in full.items]

    page1 = run(s, p.query_class(selection=p.ref_factory("sel"), limit=2))
    page2 = run(s, p.query_class(selection=p.ref_factory("sel"), limit=2, offset=2))
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
    upsert_selection(s, SEL, SelectionKind.AXIOMS, hashes, "test")

    page = run(s, ReadAxiomSelection(selection=_axiom_ref("sel")))
    assert [item.hash for item in page.items] == hashes


def test_axiom_run_raises_on_kind_mismatch(s):
    upsert_selection(s, SelectionName("foo"), SelectionKind.ENTITIES, ["ex:Dog"], "test")
    with pytest.raises(SelectionKindMismatchError):
        run(s, ReadAxiomSelection(selection=_axiom_ref("foo")))


def test_entity_run_raises_on_kind_mismatch(s):
    upsert_selection(s, SelectionName("foo"), SelectionKind.AXIOMS, ["a" * 64], "test")
    with pytest.raises(SelectionKindMismatchError):
        run(s, ReadEntitySelection(selection=_entity_ref("foo")))


def test_entity_run_returns_items_in_lex_order(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
        ],
    )
    upsert_selection(
        s,
        SEL,
        SelectionKind.ENTITIES,
        ["ex:Zebra", "ex:Antelope", "ex:Mongoose"],
        "test",
    )

    page = run(s, ReadEntitySelection(selection=_entity_ref("sel")))
    assert [str(item.iri) for item in page.items] == ["ex:Antelope", "ex:Mongoose", "ex:Zebra"]


@PARAMS
def test_run_empty_selection(s, p: _ReadParams):
    upsert_selection(s, SelectionName("empty"), p.kind, [], "test")
    page = run(s, p.query_class(selection=p.ref_factory("empty")))
    assert page.items == ()
    assert page.total_filtered == 0
    assert page.present == 0
    assert page.missing == 0


# -- entity-only behavioral tests --


def test_entity_run_present_and_missing_classified(s):
    _seed_entities_present_missing(s, SEL)
    page = run(s, ReadEntitySelection(selection=_entity_ref("sel")))
    by_iri = {item.iri: item for item in page.items}
    assert by_iri[IRI("ex:Dog")].present is True
    assert by_iri[IRI("ex:Dog")].role == EntityType.CLASS
    assert by_iri[IRI("ex:Ghost")].present is False
    assert by_iri[IRI("ex:Ghost")].role is None


def test_entity_run_show_present_returns_only_dog(s):
    _seed_entities_present_missing(s, SEL)
    page = run(s, ReadEntitySelection(selection=_entity_ref("sel"), show=ShowFilter.PRESENT))
    assert page.items[0].iri == IRI("ex:Dog")
    assert page.items[0].present is True


def test_entity_run_show_missing_returns_only_ghost(s):
    _seed_entities_present_missing(s, SEL)
    page = run(s, ReadEntitySelection(selection=_entity_ref("sel"), show=ShowFilter.MISSING))
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
    upsert_selection(s, SEL, SelectionKind.ENTITIES, ["ex:Dog"], "test")
    page = run(s, ReadEntitySelection(selection=_entity_ref("sel")))
    assert page.items[0].label == "Dog"


def test_entity_run_punned_entity_present_missing_invariant(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:X")),
            Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI("ex:X")),
        ],
    )
    upsert_selection(s, SEL, SelectionKind.ENTITIES, ["ex:X", "ex:Ghost"], "test")
    page = run(s, ReadEntitySelection(selection=_entity_ref("sel")))
    assert page.present + page.missing == page.meta.size
    assert page.present == 1
    assert page.missing == 1


# -- axiom-only behavioral assertions --


def test_axiom_run_show_present_items_not_missing(s):
    _seed_axioms_present_missing(s, SEL)
    page = run(s, ReadAxiomSelection(selection=_axiom_ref("sel"), show=ShowFilter.PRESENT))
    assert all(not item.missing for item in page.items)


def test_axiom_run_show_missing_items_all_missing(s):
    _seed_axioms_present_missing(s, SEL)
    page = run(s, ReadAxiomSelection(selection=_axiom_ref("sel"), show=ShowFilter.MISSING))
    assert all(item.missing for item in page.items)


def test_axiom_run_basic_meta_name(s):
    _seed_axioms_present_missing(s, SEL)
    page = run(s, ReadAxiomSelection(selection=_axiom_ref("sel")))
    assert page.meta.name == "sel"
