"""Smoke tests for the umbrella `run` dispatch."""

from collections import Counter

import pytest
from ontoloom.axioms.hashing import AxiomHash
from ontoloom.axioms.mutations import add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.entities.find_duplicate_entities import FindDuplicateEntities
from ontoloom.owl.axioms import AxiomTag, Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query.constraints import InEntitySelection
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.query.count_entities import CountEntities
from ontoloom.query.count_entities_by_role import CountEntitiesByRole
from ontoloom.query.dispatch import run
from ontoloom.query.find_axioms import FindAxioms
from ontoloom.query.list_axioms import ListAxioms
from ontoloom.query.list_entities import ListEntities
from ontoloom.query.stream_axioms import StreamAxioms
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.read_entity_selection import ReadEntitySelection
from ontoloom.selections.store import upsert_axiom_selection, upsert_entity_selection
from ontoloom.selections.types import (
    AxiomSelectionPage,
    EntitySelectionPage,
    SelectionName,
    SelectionNotFoundError,
)


def _seed(s):
    dog = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    cat = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat"))
    add_axioms(s, [dog, cat])
    return dog, cat


def test_dispatch_count_entities(s):
    _seed(s)
    result = run(s, CountEntities(constraints=()))
    assert isinstance(result, int)
    assert result == 2


def test_dispatch_list_entities(s):
    _seed(s)
    result = run(s, ListEntities(constraints=()))
    assert isinstance(result, list)
    assert all(isinstance(x, IRI) for x in result)
    assert result == [IRI("ex:Cat"), IRI("ex:Dog")]


def test_dispatch_count_entities_by_role(s):
    _seed(s)
    result = run(s, CountEntitiesByRole(constraints=()))
    assert isinstance(result, Counter)
    assert result[EntityType.CLASS] == 2


def test_dispatch_find_axioms(s):
    _seed(s)
    result = run(s, FindAxioms(constraints=()))
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(h, AxiomHash) for h in result)


def test_dispatch_list_axioms(s):
    _seed(s)
    result = run(s, ListAxioms(constraints=()))
    assert isinstance(result, list)
    assert len(result) == 2
    h, data = result[0]
    assert isinstance(h, AxiomHash)
    assert isinstance(data, str)


def test_dispatch_count_axioms_by_type(s):
    _seed(s)
    result = run(s, CountAxiomsByType(constraints=()))
    assert isinstance(result, Counter)
    assert result[AxiomTag.DECLARATION] == 2


def test_dispatch_stream_axioms_is_context_manager(s):
    _seed(s)
    cm = run(s, StreamAxioms(constraints=()))

    with cm as it:
        assert hasattr(it, "__next__")
        first = next(it)
        assert isinstance(first[0], AxiomHash)
        assert isinstance(first[1], str)


def test_dispatch_read_axiom_selection(s):
    dog, _ = _seed(s)
    dog_hash = HashedAxiom.of(dog).hash
    upsert_axiom_selection(s, SelectionName("ax_sel"), [dog_hash], "test")

    ref = SelectionName("ax_sel")
    result = run(s, ReadAxiomSelection(selection=ref))
    assert isinstance(result, AxiomSelectionPage)
    assert result.meta.size == 1


def test_dispatch_read_entity_selection(s):
    _seed(s)
    upsert_entity_selection(s, SelectionName("ent_sel"), ["ex:Dog"], "test")

    ref = SelectionName("ent_sel")
    result = run(s, ReadEntitySelection(selection=ref))
    assert isinstance(result, EntitySelectionPage)
    assert result.meta.size == 1


def test_dispatch_find_duplicate_entities(s):
    # Empty ontology: no annotation properties exist; result is empty but well-typed.
    result = run(s, FindDuplicateEntities(annotation_property=IRI("rdfs:label")))
    assert result.total_groups == 0
    assert result.groups == ()
    assert result.affected_iris == ()


def test_run_raises_on_nonexistent_selection_ref_in_constraints(s):
    ref = SelectionName("does_not_exist")

    with pytest.raises(SelectionNotFoundError):
        run(s, ListEntities(constraints=(InEntitySelection(name=ref),)))


def test_run_raises_on_nonexistent_selection_in_read_axiom_selection(s):
    ref = SelectionName("does_not_exist")

    with pytest.raises(SelectionNotFoundError):
        run(s, ReadAxiomSelection(selection=ref))


def test_run_raises_on_nonexistent_within_in_find_duplicate_entities(s):
    ref = SelectionName("does_not_exist")

    with pytest.raises(SelectionNotFoundError):
        run(s, FindDuplicateEntities(annotation_property=IRI("rdfs:label"), within=ref))
