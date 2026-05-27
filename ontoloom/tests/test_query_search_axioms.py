"""Tests for the SearchAxioms query: exact-then-substring annotation-text ranking."""

import pytest
from ontoloom.axioms.mutations import add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.query.constraints import InAxiomSelection
from ontoloom.query.dispatch import run
from ontoloom.query.search_axioms import SearchAxioms
from ontoloom.selections.store import upsert_axiom_selection
from ontoloom.selections.types import SelectionName


def _comment(text: str) -> Annotation:
    return Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value=text))


def _label(text: str) -> Annotation:
    return Annotation(property=IRI("rdfs:label"), value=LangLiteral(value=text))


def test_search_axioms_returns_exact_then_substring(s):
    exact = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO"),),
    )
    substring = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("needs TODO review"),),
    )
    add_axioms(s, [exact, substring])

    result = run(s, SearchAxioms(query="TODO"))

    assert len(result) == 2
    assert result[0] == HashedAxiom.of(exact).hash
    assert result[1] == HashedAxiom.of(substring).hash


def test_search_axioms_substring_only(s):
    substring = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("this is a TODO note"),),
    )
    add_axioms(s, [substring])

    result = run(s, SearchAxioms(query="TODO"))

    assert len(result) == 1
    assert result[0] == HashedAxiom.of(substring).hash


def test_search_axioms_exact_match_not_duplicated_as_substring(s):
    exact = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO"),),
    )
    add_axioms(s, [exact])

    result = run(s, SearchAxioms(query="TODO"))

    assert len(result) == 1
    assert result[0] == HashedAxiom.of(exact).hash


def test_search_axioms_case_insensitive(s):
    upper = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO"),),
    )
    add_axioms(s, [upper])

    result = run(s, SearchAxioms(query="todo"))

    assert len(result) == 1
    assert result[0] == HashedAxiom.of(upper).hash


def test_search_axioms_filters_by_properties(s):
    commented = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("x"),),
    )
    labelled = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_label("x"),),
    )
    add_axioms(s, [commented, labelled])

    result = run(
        s,
        SearchAxioms(query="x", properties=(IRI("rdfs:comment"),)),
    )

    assert len(result) == 1
    assert result[0] == HashedAxiom.of(commented).hash


def test_search_axioms_ranks_exact_before_substring_over_full_result(s):
    substrings = [
        SubClassOf(
            sub_class=IRI(f"ex:C{i}"),
            super_class=IRI("ex:Animal"),
            annotations=(_comment(f"needs TODO {i}"),),
        )
        for i in range(5)
    ]
    exact = SubClassOf(
        sub_class=IRI("ex:Exact"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO"),),
    )
    add_axioms(s, [exact, *substrings])

    result = run(s, SearchAxioms(query="TODO"))

    # Exact match ranks first (before all substring matches).
    assert result[0] == HashedAxiom.of(exact).hash

    # The full, unpaginated result holds every match exactly once.
    assert len(result) == 6
    assert len(set(result)) == 6
    expected = {HashedAxiom.of(a).hash for a in (exact, *substrings)}
    assert set(result) == expected


def test_search_axioms_empty_result(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = run(s, SearchAxioms(query="nonexistent"))
    assert result == []


def test_search_axioms_respects_within_selection(s):
    in_scope = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO"),),
    )
    out_of_scope = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO"),),
    )
    add_axioms(s, [in_scope, out_of_scope])

    upsert_axiom_selection(
        s,
        SelectionName("scoped"),
        [HashedAxiom.of(in_scope).hash],
        "test",
    )
    ref = SelectionName("scoped")

    result = run(
        s,
        SearchAxioms(query="TODO", constraints=(InAxiomSelection(name=ref),)),
    )

    assert len(result) == 1
    assert result[0] == HashedAxiom.of(in_scope).hash


def test_search_axioms_missing_selection_raises(s):
    from ontoloom.selections.types import SelectionNotFoundError

    ref = SelectionName("does_not_exist")

    with pytest.raises(SelectionNotFoundError):
        run(s, SearchAxioms(query="TODO", constraints=(InAxiomSelection(name=ref),)))
