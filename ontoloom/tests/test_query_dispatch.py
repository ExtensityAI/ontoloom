"""Smoke tests for the umbrella `run` dispatch."""

from collections import Counter

import pytest
from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import AxiomHash, HashedAxiom
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query._dispatch import run
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.query.count_entities import CountEntities
from ontoloom.query.count_entities_by_role import CountEntitiesByRole
from ontoloom.query.find_duplicate_entities import FindDuplicateEntities
from ontoloom.query.list_axiom_hashes import ListAxiomHashes
from ontoloom.query.list_axioms import ListAxioms
from ontoloom.query.list_entities import ListEntities
from ontoloom.query.read_axiom_selection import ReadAxiomSelection
from ontoloom.query.read_entity_selection import ReadEntitySelection
from ontoloom.query.stream_axioms import StreamAxioms
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import (
    AxiomSelectionPage,
    EntitySelectionPage,
    SelectionKind,
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


def test_dispatch_list_axiom_hashes(s):
    _seed(s)
    result = run(s, ListAxiomHashes(constraints=()))
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
    assert result["Declaration"] == 2


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
    upsert_selection(s, "ax_sel", SelectionKind.AXIOMS, [dog_hash], "test")

    ref = ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name="ax_sel")
    result = run(s, ReadAxiomSelection(selection=ref))
    assert isinstance(result, AxiomSelectionPage)
    assert result.meta.size == 1


def test_dispatch_read_entity_selection(s):
    _seed(s)
    upsert_selection(s, "ent_sel", SelectionKind.ENTITIES, ["ex:Dog"], "test")

    ref = ResolvedSelection(kind=SelectionKind.ENTITIES, bare_name="ent_sel")
    result = run(s, ReadEntitySelection(selection=ref))
    assert isinstance(result, EntitySelectionPage)
    assert result.meta.size == 1


def test_dispatch_find_duplicate_entities(s):
    # Empty ontology: no annotation properties exist; result is empty but well-typed.
    result = run(s, FindDuplicateEntities(annotation_property=IRI("rdfs:label")))
    assert result.total_groups == 0
    assert result.groups == ()
    assert result.affected_iris == ()


def test_dispatch_unknown_type_raises(s):
    with pytest.raises(ValueError, match="unknown query type"):
        run(s, object())  # pyright: ignore[reportCallIssue]
