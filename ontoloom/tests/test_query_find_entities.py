"""Tests for the FindEntities query (distinct IRIs, ranked then IRI-ordered)."""

from ontoloom.axioms.mutations import add_axioms
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query.dispatch import run
from ontoloom.query.find_entities import FindEntities


def test_run_empty_ontology(s):
    assert run(s, FindEntities(constraints=())) == []


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
    result = run(s, FindEntities(constraints=()))
    assert result == [IRI("ex:Antelope"), IRI("ex:Mongoose"), IRI("ex:Zebra")]


def test_run_returns_iri_typed_values(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = run(s, FindEntities(constraints=()))
    assert len(result) == 1
    assert isinstance(result[0], IRI)
