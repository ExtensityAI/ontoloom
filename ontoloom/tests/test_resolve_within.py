import pytest
from ontoloom.axioms.hashing import AxiomHash
from ontoloom.owl.iri import IRI
from ontoloom.query.constraints import InAxiomSelection, InEntitySelection
from ontoloom.query.dispatch import resolve_within
from ontoloom.selections.store import upsert_axiom_selection, upsert_entity_selection
from ontoloom.selections.types import SelectionName, SelectionNotFoundError


def test_resolve_within_axiom(s):
    upsert_axiom_selection(s, SelectionName("axs"), [AxiomHash("a" * 64)], "t")
    assert resolve_within(s, SelectionName("axs")) == InAxiomSelection(name=SelectionName("axs"))


def test_resolve_within_entity(s):
    upsert_entity_selection(s, SelectionName("ents"), [IRI("ex:Dog")], "t")
    assert resolve_within(s, SelectionName("ents")) == InEntitySelection(name=SelectionName("ents"))


def test_resolve_within_missing(s):
    with pytest.raises(SelectionNotFoundError):
        resolve_within(s, SelectionName("nope"))
