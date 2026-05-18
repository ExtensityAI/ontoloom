"""Tests for the FindDuplicateEntities query."""

import pytest
from ontoloom.axioms.store import add_axioms
from ontoloom.owl.axioms import AnnotationAssertion, Declaration
from ontoloom.owl.iri import IRI, RDFS_LABEL
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.query.find_duplicate_entities import FindDuplicateEntities
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import EntitySelectionName, SelectionKind, SelectionName
from pydantic import ValidationError


def _ref(name: str) -> EntitySelectionName:
    return EntitySelectionName(f"entities:{name}")


def _decl(iri: str) -> Declaration:
    return Declaration(entity_type=EntityType.CLASS, iri=IRI(iri))


def _label(iri: str, text: str) -> AnnotationAssertion:
    return AnnotationAssertion(
        property=IRI(RDFS_LABEL),
        subject=IRI(iri),
        value=LangLiteral(value=text, lang="en"),
    )


# -- field validator: wrong kind --


def test_field_validator_rejects_axiom_kind():
    with pytest.raises(ValidationError):
        FindDuplicateEntities(
            annotation_property=IRI(RDFS_LABEL),
            within="axioms:foo",  # pyright: ignore[reportArgumentType]
        )


def test_field_validator_accepts_none_within():
    q = FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL))
    assert q.within is None


def test_field_validator_accepts_entity_within():
    q = FindDuplicateEntities(
        annotation_property=IRI(RDFS_LABEL),
        within=_ref("foo"),
    )
    assert q.within is not None
    assert q.within.kind == SelectionKind.ENTITIES


# -- render snapshots --


def test_render_without_scope():
    compiled = (FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL))).render()
    assert compiled.sql == (
        "SELECT et.text, et.entity_iri"
        " FROM entity_text et"
        " WHERE et.property = ?"
        "   AND EXISTS ("
        "     SELECT 1 FROM entity_text et2"
        "     WHERE et2.property = ? AND et2.text = et.text AND et2.entity_iri != et.entity_iri"
        "   )"
        " GROUP BY et.text, et.entity_iri"
        " ORDER BY et.text, et.entity_iri"
    )
    assert compiled.params == (RDFS_LABEL, RDFS_LABEL)


def test_render_with_scope():
    compiled = (
        FindDuplicateEntities(
            annotation_property=IRI(RDFS_LABEL),
            within=_ref("sel"),
        )
    ).render()
    assert compiled.sql == (
        "SELECT et.text, et.entity_iri"
        " FROM entity_text et"
        " WHERE et.property = ?"
        " AND EXISTS (SELECT 1 FROM selection_items si"
        " WHERE si.item = et.entity_iri AND si.selection_name = ?)"
        "   AND EXISTS ("
        "     SELECT 1 FROM entity_text et2"
        "     WHERE et2.property = ? AND et2.text = et.text AND et2.entity_iri != et.entity_iri"
        " AND EXISTS (SELECT 1 FROM selection_items si2"
        " WHERE si2.item = et2.entity_iri AND si2.selection_name = ?)"
        "   )"
        " GROUP BY et.text, et.entity_iri"
        " ORDER BY et.text, et.entity_iri"
    )
    assert compiled.params == (RDFS_LABEL, "sel", RDFS_LABEL, "sel")


# -- integration tests --


def test_run_empty_ontology(s):
    result = (FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL)))._run(s)
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
    result = (FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL)))._run(s)
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
    result = (FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL)))._run(s)
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
    result = (FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL)))._run(s)
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
    upsert_selection(s, SelectionName("scope"), SelectionKind.ENTITIES, ["ex:A", "ex:B"], "test")

    result = FindDuplicateEntities(
        annotation_property=IRI(RDFS_LABEL),
        within=_ref("scope"),
    )._run(s)
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
    result = (FindDuplicateEntities(annotation_property=IRI(RDFS_LABEL)))._run(s)
    assert len(result.affected_iris) == len(set(result.affected_iris))
    assert set(result.affected_iris) == {"ex:A", "ex:B", "ex:C", "ex:D"}
