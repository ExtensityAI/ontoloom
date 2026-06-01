"""Tests for the FindDuplicateEntities query."""

import pytest
from ontoloom.axioms.mutations import add_axioms
from ontoloom.entities.find_duplicate_entities import FindDuplicateEntities
from ontoloom.owl.axioms import AnnotationAssertion, Declaration
from ontoloom.owl.iri import IRI, RDFS_LABEL
from ontoloom.owl.literals import BCP47Tag, LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.query.dispatch import execute
from ontoloom.selections.store import upsert_entity_selection
from ontoloom.selections.types import SelectionName
from pydantic import ValidationError


def _ref(name: str) -> SelectionName:
    return SelectionName(name)


def _decl(iri: str) -> Declaration:
    return Declaration(entity_type=EntityType.CLASS, iri=IRI(iri))


def _label(iri: str, text: str) -> AnnotationAssertion:
    return AnnotationAssertion(
        property=IRI(RDFS_LABEL),
        subject=IRI(iri),
        value=LangLiteral(value=text, lang=BCP47Tag("en")),
    )


# -- field validator: name shape --


def test_field_validator_rejects_invalid_name():
    with pytest.raises(ValidationError):
        FindDuplicateEntities(
            annotation_property=IRI(RDFS_LABEL),
            within="not a valid name",  # pyright: ignore[reportArgumentType]
        )


def test_field_validator_accepts_none_within():
    q = FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL))
    assert q.within is None


def test_field_validator_accepts_within():
    q = FindDuplicateEntities(
        annotation_property=IRI(RDFS_LABEL),
        within=_ref("foo"),
    )
    assert q.within == SelectionName("foo")


# -- integration tests --


def test_run_empty_ontology(s):
    result = execute(s, FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL)))
    assert result.groups == ()
    assert result.total_groups == 0
    assert result.affected_iris == ()


def test_run_no_duplicates(s):
    add_axioms(
        s,
        [
            _decl("ex:A"),
            _decl("ex:B"),
            _label("ex:A", "Alpha"),
            _label("ex:B", "Beta"),
        ],
    )
    result = execute(s, FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL)))
    assert result.groups == ()
    assert result.total_groups == 0


def test_run_one_duplicate_group(s):
    add_axioms(
        s,
        [
            _decl("ex:A"),
            _decl("ex:B"),
            _label("ex:A", "Same"),
            _label("ex:B", "Same"),
        ],
    )
    result = execute(s, FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL)))
    assert result.total_groups == 1
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.value == "Same"
    assert set(group.iris) == {"ex:A", "ex:B"}
    assert set(result.affected_iris) == {"ex:A", "ex:B"}


def test_run_groups_sorted_by_size_desc(s):
    add_axioms(
        s,
        [
            _decl("ex:A"),
            _decl("ex:B"),
            _decl("ex:C"),
            _decl("ex:D"),
            _decl("ex:E"),
            _label("ex:A", "Pair"),
            _label("ex:B", "Pair"),
            _label("ex:C", "Triple"),
            _label("ex:D", "Triple"),
            _label("ex:E", "Triple"),
        ],
    )
    result = execute(s, FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL)))
    assert result.total_groups == 2
    assert result.groups[0].value == "Triple"
    assert len(result.groups[0].iris) == 3
    assert result.groups[1].value == "Pair"
    assert len(result.groups[1].iris) == 2


def test_run_scoped_to_entity_selection(s):
    add_axioms(
        s,
        [
            _decl("ex:A"),
            _decl("ex:B"),
            _decl("ex:C"),
            _label("ex:A", "Shared"),
            _label("ex:B", "Shared"),
            _label("ex:C", "Shared"),
        ],
    )
    upsert_entity_selection(s, SelectionName("scope"), ["ex:A", "ex:B"], "test")

    result = execute(
        s,
        FindDuplicateEntities(
            annotation_property=IRI(RDFS_LABEL),
            within=_ref("scope"),
        ),
    )
    assert result.total_groups == 1
    group = result.groups[0]
    assert group.value == "Shared"
    assert set(group.iris) == {"ex:A", "ex:B"}


def test_run_affected_iris_has_no_duplicates(s):
    add_axioms(
        s,
        [
            _decl("ex:A"),
            _decl("ex:B"),
            _decl("ex:C"),
            _decl("ex:D"),
            _label("ex:A", "Group1"),
            _label("ex:B", "Group1"),
            _label("ex:C", "Group2"),
            _label("ex:D", "Group2"),
        ],
    )
    result = execute(s, FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL)))
    assert len(result.affected_iris) == len(set(result.affected_iris))
    assert set(result.affected_iris) == {"ex:A", "ex:B", "ex:C", "ex:D"}
