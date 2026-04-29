"""Integration tests for MCP tool functions.

Each test calls a tool function directly (the same callable wrapped by
`create_tool`) to exercise input validation, formatting, and error translation.
"""

import pytest
from fastmcp.exceptions import ToolError
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.axioms import Declaration, SubClassOf
from ontoloom.ontology.models.expressions import NamedClass
from ontoloom.ontology.models.literals import IRI, EntityType
from ontoloom.ontology.types import LockedSelection
from ontoloom_mcp.components.errors import translate_errors
from ontoloom_mcp.tools.axioms.add_axioms import add_axioms
from ontoloom_mcp.tools.axioms.rm_axioms import rm_axioms
from ontoloom_mcp.tools.entities.get_entity import get_entity
from ontoloom_mcp.tools.entities.search_entities import search_entities
from ontoloom_mcp.tools.ontology.create_ontology import create_ontology
from ontoloom_mcp.tools.selections.read_selection import read_selection


@pytest.fixture()
def empty_db(tmp_path):
    path = tmp_path / "test.ontology.db"
    Ontology.create(path)
    return path


@pytest.fixture()
def populated_db(empty_db):
    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            SubClassOf(
                sub_class=NamedClass(iri=IRI("ex:Dog")),
                super_class=NamedClass(iri=IRI("ex:Animal")),
            ),
        ],
    )
    return empty_db


# -- Happy paths --


def test_create_ontology_creates_file(tmp_path):
    path = tmp_path / "new.ontology.db"
    result = create_ontology(path=path)
    assert path.exists()
    assert "Created ontology" in result


def test_add_axioms_returns_diff(empty_db):
    result = add_axioms(
        path=empty_db,
        axioms=[Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))],
    )
    assert "Added 1, skipped 0" in result
    assert "+" in result


def test_get_entity_returns_info(populated_db):
    result = get_entity(path=populated_db, iri=IRI("ex:Dog"))
    assert "ex:Dog" in result
    assert "Class" in result


def test_search_entities_creates_selection(populated_db):
    result = search_entities(path=populated_db, into="dogs", query="Dog")
    assert "dogs" in result
    assert "sel@" in result


def test_read_selection_after_search(populated_db):
    search_entities(path=populated_db, into="dogs", query="Dog")
    result = read_selection(path=populated_db, name="dogs")
    assert "ex:Dog" in result


# -- Error translation --


def test_create_ontology_existing_file_raises(empty_db):
    wrapped = translate_errors(create_ontology)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=empty_db)
    assert "already exists" in str(exc_info.value)


def test_get_entity_not_found_includes_suggestion(populated_db):
    # IRI that doesn't exist but whose local name is a substring of an existing
    # entity's text should produce a suggestion.
    result = get_entity(path=populated_db, iri=IRI("ex:Anima"))
    assert "Not found" in result
    assert "Similar entities" in result
    assert "ex:Animal" in result


def test_read_selection_not_found_translates(populated_db):
    wrapped = translate_errors(read_selection)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=populated_db, name="nonexistent")
    msg = str(exc_info.value)
    assert "nonexistent" in msg
    assert "search_entities" in msg or "match_axioms" in msg


def test_rm_axioms_stale_selection_translates(populated_db):
    # Create an axiom selection, then mutate it, then try to use the stale hash.
    search_entities(path=populated_db, into="dogs_ent", query="Dog")
    # Manually create an axiom selection from those entities (use create_selection directly)
    from ontoloom_mcp.tools.selections.create_selection import create_selection

    create_selection(path=populated_db, name="dogs_ax", axioms_for="dogs_ent")
    # Build a LockedSelection with a wrong hash to trigger StaleSelectionError.
    stale = LockedSelection("dogs_ax@deadbeef")

    wrapped = translate_errors(rm_axioms)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=populated_db, within=stale)
    assert "changed" in str(exc_info.value)


def test_rm_axioms_rejects_both_inputs():
    wrapped = translate_errors(rm_axioms)
    with pytest.raises(ToolError):
        wrapped(
            path="dummy",
            hash_prefixes=["abc"],
            within=LockedSelection("foo@deadbeef"),
        )
