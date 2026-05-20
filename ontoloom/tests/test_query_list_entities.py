"""Tests for the ListEntities query."""

from ontoloom.axioms.store import add_axioms
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query.constraints import AlwaysFalse
from ontoloom.query.dispatch import run
from ontoloom.query.list_entities import ListEntities


def test_run_empty_ontology(s):
    assert run(s, ListEntities(constraints=())) == []


def test_run_lists_in_iri_order(s):
    # Insert out-of-order; results must come back sorted.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
        ],
    )
    result = run(s, ListEntities(constraints=()))
    assert result == [IRI("ex:Antelope"), IRI("ex:Mongoose"), IRI("ex:Zebra")]


def test_run_pagination_stable(s):
    # Six entities; verify page1 + page2 cover the first 4 with no overlap.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:D")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:E")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:F")),
        ],
    )

    page1 = run(s, ListEntities(constraints=(), limit=2))
    page2 = run(s, ListEntities(constraints=(), limit=2, offset=2))

    assert page1 == [IRI("ex:A"), IRI("ex:B")]
    assert page2 == [IRI("ex:C"), IRI("ex:D")]
    assert set(page1).isdisjoint(page2)


def test_run_pagination_full_walk(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
        ],
    )

    full = run(s, ListEntities(constraints=()))
    paged = (
        run(s, ListEntities(constraints=(), limit=1))
        + run(s, ListEntities(constraints=(), limit=1, offset=1))
        + run(s, ListEntities(constraints=(), limit=1, offset=2))
    )
    assert paged == full


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert run(s, ListEntities(constraints=(AlwaysFalse(),))) == []


def test_run_returns_iri_typed_values(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = run(s, ListEntities(constraints=()))
    assert len(result) == 1
    assert isinstance(result[0], IRI)
