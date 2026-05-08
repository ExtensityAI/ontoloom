"""Integration tests for MCP tool functions.

Each test calls a tool function directly (the same callable wrapped by
`create_tool`) to exercise input validation, formatting, and error translation.
"""

import pytest
from fastmcp.exceptions import ToolError
from ontoloom.connection import Ontology
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.selections.types import LockedSelection, SelectionName
from ontoloom_mcp.components.confirmation import ConfirmationRequiredError
from ontoloom_mcp.components.errors import translate_errors
from ontoloom_mcp.tools.axioms.add_axioms import add_axioms
from ontoloom_mcp.tools.axioms.remove_axioms import remove_axioms
from ontoloom_mcp.tools.axioms.rename_iri import rename_iri
from ontoloom_mcp.tools.entities.get_entity import get_entity
from ontoloom_mcp.tools.entities.search_entities import search_entities
from ontoloom_mcp.tools.ontology.create_ontology import create_ontology
from ontoloom_mcp.tools.prefixes.set_prefix import set_prefix
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
                sub_class=IRI("ex:Dog"),
                super_class=IRI("ex:Animal"),
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
    result = search_entities(path=populated_db, into=SelectionName("dogs"), query="Dog")
    assert "dogs@" in result


def test_read_selection_after_search(populated_db):
    search_entities(path=populated_db, into=SelectionName("dogs"), query="Dog")
    result = read_selection(path=populated_db, name=SelectionName("dogs"))
    assert "ex:Dog" in result


# -- Error translation --


def test_create_ontology_existing_file_raises(empty_db):
    wrapped = translate_errors(create_ontology)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=empty_db)
    assert "already exists" in str(exc_info.value)


def test_get_entity_not_found_includes_suggestion(populated_db):
    # IRI that doesn't exist but whose local name is a substring of an existing
    # entity's text should produce a ToolError with a "did you mean" suggestion.
    wrapped = translate_errors(get_entity)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=populated_db, iri=IRI("ex:Anima"))
    msg = str(exc_info.value)
    assert "not found" in msg
    assert "Similar entities" in msg
    assert "ex:Animal" in msg


def test_read_selection_not_found_translates(populated_db):
    wrapped = translate_errors(read_selection)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=populated_db, name="nonexistent")
    msg = str(exc_info.value)
    assert "nonexistent" in msg
    assert "search_entities" in msg or "match_axioms" in msg


def test_remove_axioms_stale_selection_translates(populated_db):
    # Create an axiom selection, then mutate it, then try to use the stale hash.
    search_entities(path=populated_db, into=SelectionName("dogs_ent"), query="Dog")
    # Manually create an axiom selection from those entities (use create_selection directly)
    from ontoloom.selections.expr import AxiomsForExpr
    from ontoloom_mcp.tools.selections.create_selection import create_selection

    create_selection(
        path=populated_db,
        name=SelectionName("dogs_ax"),
        expr=AxiomsForExpr(axioms_for=SelectionName("dogs_ent")),
    )
    # Build a LockedSelection with a wrong hash to trigger StaleSelectionError.
    stale = LockedSelection("dogs_ax@deadbeef")

    wrapped = translate_errors(remove_axioms)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=populated_db, within=stale)
    assert "changed" in str(exc_info.value)


def test_remove_axioms_rejects_both_inputs():
    wrapped = translate_errors(remove_axioms)
    with pytest.raises(ToolError):
        wrapped(
            path="dummy",
            axiom_hashes=["abc"],
            within=LockedSelection("foo@deadbeef"),
        )


def test_axiom_dispatch_failure_renders_focused_mcp_message():
    """A bad axiom dict, validated through the Axiom union adapter, should
    raise UnionDispatchError; the MCP-layer formatter renders it as a focused
    single-line message — not the multi-KB union signature dump."""
    from ontoloom.errors import UnionDispatchError
    from ontoloom.owl.axioms import Axiom
    from ontoloom_mcp.components.errors import format_error
    from pydantic import TypeAdapter

    adapter: TypeAdapter[Axiom] = TypeAdapter(Axiom)
    with pytest.raises(UnionDispatchError) as exc_info:
        adapter.validate_python({"sub_class": "ex:Dog"})

    msg = format_error(exc_info.value)
    assert "Axiom" in msg
    assert "SubClassOf" in msg
    assert "super_class" in msg
    # No multi-line signature dump:
    assert "required=" not in msg
    assert "optional=" not in msg
    assert "\n" not in msg


# -- set_prefix confirmation flow --


def test_set_prefix_new_prefix_succeeds_without_confirm(empty_db):
    result = set_prefix(path=empty_db, name="myns", iri="http://example.org/myns/")
    assert "myns" in result
    assert "http://example.org/myns/" in result


def test_set_prefix_same_iri_returns_unchanged(empty_db):
    set_prefix(path=empty_db, name="foo", iri="http://example.org/foo/")
    result = set_prefix(path=empty_db, name="foo", iri="http://example.org/foo/")
    assert "(unchanged)" in result


def test_set_prefix_reassign_unused_prefix_no_confirm_required(empty_db):
    # Set a fresh prefix, then reassign before any entity uses it.
    set_prefix(path=empty_db, name="foo", iri="http://example.org/foo/")
    result = set_prefix(path=empty_db, name="foo", iri="http://example.org/foo2/")
    assert "foo" in result
    assert "http://example.org/foo2/" in result


def test_set_prefix_reassign_in_use_without_confirm_raises(populated_db):
    # populated_db has ex:Dog, ex:Animal, etc. as entities. After registering 'ex'
    # as a prefix mapping, those entities count as "in use" of that prefix.
    set_prefix(path=populated_db, name="ex", iri="http://example.org/")

    with pytest.raises(ConfirmationRequiredError) as exc_info:
        set_prefix(path=populated_db, name="ex", iri="http://other.example.org/")
    assert exc_info.value.token
    assert "confirm=" in str(exc_info.value)


def test_set_prefix_reassign_in_use_with_correct_token_succeeds(populated_db):
    set_prefix(path=populated_db, name="ex", iri="http://example.org/")

    with pytest.raises(ConfirmationRequiredError) as exc_info:
        set_prefix(path=populated_db, name="ex", iri="http://other.example.org/")
    token = exc_info.value.token

    result = set_prefix(
        path=populated_db,
        name="ex",
        iri="http://other.example.org/",
        confirm=token,
    )
    assert "ex" in result
    assert "http://other.example.org/" in result


def test_set_prefix_reassign_in_use_with_wrong_token_raises(populated_db):
    set_prefix(path=populated_db, name="ex", iri="http://example.org/")

    with pytest.raises(ConfirmationRequiredError):
        set_prefix(
            path=populated_db,
            name="ex",
            iri="http://other.example.org/",
            confirm="00000000",
        )
    # State unchanged: ex still maps to its original IRI.
    from ontoloom.prefixes import list_prefixes
    from ontoloom.transactions import session

    with session(Ontology(populated_db)) as s:
        prefixes = list_prefixes(s)
        s.commit()
    assert prefixes["ex"] == "http://example.org/"


# -- rename_iri confirmation flow --


def test_rename_iri_no_collision_succeeds_without_confirm(populated_db):
    result = rename_iri(path=populated_db, old_iri=IRI("ex:Dog"), new_iri=IRI("ex:Puppy"))
    assert "ex:Dog" in result
    assert "ex:Puppy" in result
    assert "replaced" in result


def test_rename_iri_no_op_when_iri_absent(populated_db):
    result = rename_iri(path=populated_db, old_iri=IRI("ex:NotPresent"), new_iri=IRI("ex:Other"))
    assert "No-op" in result


def test_rename_iri_collision_without_confirm_raises(populated_db):
    # Both ex:Dog (Class) declaration and ex:Animal (Class) declaration exist.
    # Renaming ex:Dog -> ex:Animal collides on the Declaration axiom.
    with pytest.raises(ConfirmationRequiredError) as exc_info:
        rename_iri(path=populated_db, old_iri=IRI("ex:Dog"), new_iri=IRI("ex:Animal"))
    assert exc_info.value.token
    assert "confirm=" in str(exc_info.value)


def test_rename_iri_collision_with_correct_token_succeeds(populated_db):
    with pytest.raises(ConfirmationRequiredError) as exc_info:
        rename_iri(path=populated_db, old_iri=IRI("ex:Dog"), new_iri=IRI("ex:Animal"))
    token = exc_info.value.token

    result = rename_iri(
        path=populated_db,
        old_iri=IRI("ex:Dog"),
        new_iri=IRI("ex:Animal"),
        confirm=token,
    )
    assert "ex:Dog" in result
    assert "ex:Animal" in result
    assert "merged" in result


def test_rename_iri_collision_with_wrong_token_raises(populated_db):
    with pytest.raises(ConfirmationRequiredError):
        rename_iri(
            path=populated_db,
            old_iri=IRI("ex:Dog"),
            new_iri=IRI("ex:Animal"),
            confirm="00000000",
        )
