import pytest
from ontoloom.axioms.store import add_axioms
from ontoloom.connection import Ontology
from ontoloom.entities.store import find_duplicate_entities
from ontoloom.owl.axioms import AnnotationAssertion, Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import SelectionKind


@pytest.fixture()
def ont(tmp_path):
    path = tmp_path / "test.ontology.db"
    Ontology.create(path)
    with Ontology(path) as o:
        yield o


def _add_label(ont, subject: str, label: str):
    add_axioms(
        ont,
        [
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI(subject),
                value=LangLiteral(value=label),
            ),
        ],
    )


def test_find_duplicates_basic(ont):
    add_axioms(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
        ],
    )
    _add_label(ont, "ex:A", "transport")
    _add_label(ont, "ex:B", "transport")
    _add_label(ont, "ex:C", "unique")

    result = find_duplicate_entities(ont, annotation_property="rdfs:label")

    assert result.total_groups == 1
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.value == "transport"
    assert set(group.iris) == {"ex:A", "ex:B"}
    assert "ex:C" not in result.affected_iris


def test_find_duplicates_multiple_groups(ont):
    add_axioms(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:D")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:E")),
        ],
    )
    # "alpha" shared by 3 entities
    _add_label(ont, "ex:A", "alpha")
    _add_label(ont, "ex:B", "alpha")
    _add_label(ont, "ex:C", "alpha")
    # "beta" shared by 2 entities
    _add_label(ont, "ex:D", "beta")
    _add_label(ont, "ex:E", "beta")

    result = find_duplicate_entities(ont, annotation_property="rdfs:label")

    assert result.total_groups == 2
    # Ordered by count DESC: alpha (3) before beta (2)
    assert result.groups[0].value == "alpha"
    assert len(result.groups[0].iris) == 3
    assert result.groups[1].value == "beta"
    assert len(result.groups[1].iris) == 2


def test_find_duplicates_no_duplicates(ont):
    add_axioms(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        ],
    )
    _add_label(ont, "ex:A", "unique_one")
    _add_label(ont, "ex:B", "unique_two")

    result = find_duplicate_entities(ont, annotation_property="rdfs:label")

    assert result.total_groups == 0
    assert result.groups == ()
    assert result.affected_iris == ()


def test_find_duplicates_within(ont):
    add_axioms(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:D")),
        ],
    )
    # A and B share "dup", C and D share "dup" too
    _add_label(ont, "ex:A", "dup")
    _add_label(ont, "ex:B", "dup")
    _add_label(ont, "ex:C", "dup")
    _add_label(ont, "ex:D", "dup")

    # Selection contains only A and B
    upsert_selection(ont, "subset", SelectionKind.ENTITIES, ["ex:A", "ex:B"], "test")

    result = find_duplicate_entities(ont, annotation_property="rdfs:label", within="subset")

    assert result.total_groups == 1
    group = result.groups[0]
    assert group.value == "dup"
    assert set(group.iris) == {"ex:A", "ex:B"}
    assert "ex:C" not in result.affected_iris
    assert "ex:D" not in result.affected_iris
