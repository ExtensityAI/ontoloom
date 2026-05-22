"""Tests for the SearchAxioms query: exact-then-substring annotation-text ranking."""

import pytest
from ontoloom.axioms.mutations import add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.query.constraints import InSelection
from ontoloom.query.dispatch import run
from ontoloom.query.search_axioms import SearchAxioms, SearchAxiomsHit, SearchAxiomsResult
from ontoloom.selections.persistence import upsert_selection
from ontoloom.selections.types import AxiomSelectionName, SelectionKind, SelectionName


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

    result = run(s, SearchAxioms(query="TODO", limit=10))

    assert isinstance(result, SearchAxiomsResult)
    assert result.total == 2
    assert len(result.hits) == 2
    assert all(isinstance(h, SearchAxiomsHit) for h in result.hits)
    assert result.hits[0].hash == HashedAxiom.of(exact).hash
    assert result.hits[0].rank == 0
    assert result.hits[1].hash == HashedAxiom.of(substring).hash
    assert result.hits[1].rank == 1


def test_search_axioms_substring_only(s):
    substring = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("this is a TODO note"),),
    )
    add_axioms(s, [substring])

    result = run(s, SearchAxioms(query="TODO", limit=10))

    assert result.total == 1
    assert result.hits[0].hash == HashedAxiom.of(substring).hash
    assert result.hits[0].rank == 1


def test_search_axioms_exact_match_not_duplicated_as_substring(s):
    exact = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO"),),
    )
    add_axioms(s, [exact])

    result = run(s, SearchAxioms(query="TODO", limit=10))

    assert result.total == 1
    assert result.hits[0].rank == 0


def test_search_axioms_case_insensitive(s):
    upper = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO"),),
    )
    add_axioms(s, [upper])

    result = run(s, SearchAxioms(query="todo", limit=10))

    assert result.total == 1
    assert result.hits[0].rank == 0


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
        SearchAxioms(query="x", properties=(IRI("rdfs:comment"),), limit=10),
    )

    assert result.total == 1
    assert result.hits[0].hash == HashedAxiom.of(commented).hash


def test_search_axioms_paginates_after_rank(s):
    axioms = [
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
    add_axioms(s, [exact, *axioms])

    page1 = run(s, SearchAxioms(query="TODO", limit=2, offset=0))
    page2 = run(s, SearchAxioms(query="TODO", limit=2, offset=2))
    page3 = run(s, SearchAxioms(query="TODO", limit=2, offset=4))

    assert page1.total == 6
    assert page2.total == 6
    assert page3.total == 6

    assert len(page1.hits) == 2
    assert len(page2.hits) == 2
    assert len(page3.hits) == 2

    # Exact match is first.
    assert page1.hits[0].rank == 0
    # All other hits are substring (rank=1).
    assert all(h.rank == 1 for h in (*page1.hits[1:], *page2.hits, *page3.hits))

    all_hashes = [h.hash for h in (*page1.hits, *page2.hits, *page3.hits)]
    assert len(set(all_hashes)) == 6


def test_search_axioms_empty_result(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = run(s, SearchAxioms(query="nonexistent", limit=10))
    assert result.total == 0
    assert result.hits == ()


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

    upsert_selection(
        s,
        SelectionName("scoped"),
        SelectionKind.AXIOMS,
        [HashedAxiom.of(in_scope).hash],
        "test",
    )
    ref = AxiomSelectionName("axioms:scoped")

    result = run(
        s,
        SearchAxioms(query="TODO", constraints=(InSelection(ref=ref),), limit=10),
    )

    assert result.total == 1
    assert result.hits[0].hash == HashedAxiom.of(in_scope).hash


def test_search_axioms_total_independent_of_pagination(s):
    axioms = [
        SubClassOf(
            sub_class=IRI(f"ex:C{i}"),
            super_class=IRI("ex:Animal"),
            annotations=(_comment("contains TODO mark"),),
        )
        for i in range(4)
    ]
    add_axioms(s, axioms)

    page = run(s, SearchAxioms(query="TODO", limit=2))
    assert page.total == 4
    assert len(page.hits) == 2


def test_search_axioms_missing_selection_raises(s):
    from ontoloom.selections.types import SelectionNotFoundError

    ref = AxiomSelectionName("axioms:does_not_exist")

    with pytest.raises(SelectionNotFoundError):
        run(s, SearchAxioms(query="TODO", constraints=(InSelection(ref=ref),)))
