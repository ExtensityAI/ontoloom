import pytest
from ontoloom.ontology import axioms, entities, selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.axioms import AnnotationAssertion, Declaration
from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.literals import IRI, LangLiteral
from ontoloom.ontology.types import SelectionKind


@pytest.fixture()
def ont(tmp_path):
    path = tmp_path / "test.ontology.db"
    Ontology.create(path)
    with Ontology(path) as o:
        yield o


def _add_label(ont, subject: str, label: str):
    axioms.add(
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
    axioms.add(
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

    result = entities.find_duplicates(ont, annotation_property="rdfs:label")

    assert result.total_groups == 1
    assert len(result.groups) == 1
    text, iris = result.groups[0]
    assert text == "transport"
    assert set(iris) == {"ex:A", "ex:B"}
    assert "ex:C" not in result.affected_iris


def test_find_duplicates_multiple_groups(ont):
    axioms.add(
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

    result = entities.find_duplicates(ont, annotation_property="rdfs:label")

    assert result.total_groups == 2
    # Ordered by count DESC: alpha (3) before beta (2)
    assert result.groups[0][0] == "alpha"
    assert len(result.groups[0][1]) == 3
    assert result.groups[1][0] == "beta"
    assert len(result.groups[1][1]) == 2


def test_find_duplicates_no_duplicates(ont):
    axioms.add(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        ],
    )
    _add_label(ont, "ex:A", "unique_one")
    _add_label(ont, "ex:B", "unique_two")

    result = entities.find_duplicates(ont, annotation_property="rdfs:label")

    assert result.total_groups == 0
    assert result.groups == []
    assert result.affected_iris == []


def test_find_duplicates_within(ont):
    axioms.add(
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
    selections.write(ont, "subset", SelectionKind.ENTITIES, ["ex:A", "ex:B"], "test")

    result = entities.find_duplicates(ont, annotation_property="rdfs:label", within="subset")

    assert result.total_groups == 1
    text, iris = result.groups[0]
    assert text == "dup"
    assert set(iris) == {"ex:A", "ex:B"}
    assert "ex:C" not in result.affected_iris
    assert "ex:D" not in result.affected_iris
