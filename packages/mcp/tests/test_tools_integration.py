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
from ontoloom.selections.types import EntitySelectionName, SelectionName
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
    set_prefix(path=path, name="ex", iri="http://example.org/")
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
    result = search_entities(
        path=populated_db,
        into=EntitySelectionName("entities:dogs"),
        query="Dog",
    )
    assert "dogs@" in result


def test_read_selection_after_search(populated_db):
    search_entities(
        path=populated_db,
        into=EntitySelectionName("entities:dogs"),
        query="Dog",
    )
    result = read_selection(path=populated_db, name=EntitySelectionName("entities:dogs"))
    assert "ex:Dog" in result


# -- Error translation --


def test_create_ontology_existing_file_raises(empty_db):
    wrapped = translate_errors(create_ontology)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=empty_db)
    assert "already exists" in str(exc_info.value)


def test_create_ontology_missing_parent_dir_echoes_path(tmp_path):
    wrapped = translate_errors(create_ontology)
    target = tmp_path / "no_such" / "nested" / "x.db"
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=target)
    msg = str(exc_info.value)
    assert "does not exist" in msg
    assert str(target.parent) in msg


def test_session_against_non_database_file_echoes_path(tmp_path):
    from ontoloom.connection import Ontology, session

    not_a_db = tmp_path / "garbage.db"
    not_a_db.write_bytes(b"this is not a sqlite database")
    ont = Ontology(path=not_a_db)
    with pytest.raises(Exception) as exc_info, session(ont):
        pass
    msg = str(exc_info.value)
    assert str(not_a_db) in msg


def test_add_axioms_rejects_undeclared_prefix(empty_db):
    wrapped = translate_errors(add_axioms)
    with pytest.raises(ToolError) as exc_info:
        wrapped(
            path=empty_db,
            axioms=[Declaration(entity_type=EntityType.CLASS, iri=IRI("ghost:NoSuchPrefix"))],
        )
    msg = str(exc_info.value)
    assert "ghost" in msg
    assert "Undeclared prefix" in msg
    assert "set_prefix" in msg


def test_add_axioms_accepts_builtin_prefixes(empty_db):
    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
        ],
    )
    from ontoloom.owl.axioms import AnnotationAssertion
    from ontoloom.owl.literals import LangLiteral

    result = add_axioms(
        path=empty_db,
        axioms=[
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Dog"),
                value=LangLiteral(value="Dog"),
            )
        ],
    )
    assert "Added 1" in result


def test_find_duplicates_within_missing_selection_translates(populated_db):
    from ontoloom_mcp.tools.entities.find_duplicates import find_duplicates

    wrapped = translate_errors(find_duplicates)
    with pytest.raises(ToolError) as exc_info:
        wrapped(
            path=populated_db,
            into=EntitySelectionName("entities:dups"),
            annotation_property=IRI("rdfs:label"),
            within=EntitySelectionName("entities:nonexistent"),
        )
    msg = str(exc_info.value)
    assert "nonexistent" in msg
    assert "search_entities" in msg or "match_axioms" in msg


def test_annotate_axiom_reports_applied_counts(populated_db):
    from ontoloom.axioms.types import AddAnnotation, RemoveAnnotation
    from ontoloom.owl.annotations import Annotation
    from ontoloom.owl.literals import LangLiteral
    from ontoloom_mcp.tools.axioms.annotate_axiom import annotate_axiom

    note = LangLiteral(value="A subclass relation.")
    add_ann = Annotation(property=IRI("rdfs:comment"), value=note)
    # Find the SubClassOf axiom hash
    from ontoloom.owl.axioms import SubClassOf as _SubClassOf

    sub_axiom = _SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    from ontoloom.hashing import HashedAxiom

    target_hash = HashedAxiom.of(sub_axiom).hash

    # Fresh add: +1 added, no skipped
    fresh = annotate_axiom(
        path=populated_db,
        axiom_hash=target_hash[:8],
        changes=(AddAnnotation(add=add_ann),),
    )
    assert "+1 added, 0 removed" in fresh
    assert "already present" not in fresh
    assert "absent" not in fresh

    # Duplicate adds: applied 0 fresh, 1 already present
    dup = annotate_axiom(
        path=populated_db,
        axiom_hash=target_hash[:8],
        changes=(AddAnnotation(add=add_ann), AddAnnotation(add=add_ann)),
    )
    assert "+0 added, 0 removed" in dup
    assert "1 already present" in dup

    # Remove an absent annotation: 0 removed, 1 absent
    absent = LangLiteral(value="not present")
    absent_ann = Annotation(property=IRI("rdfs:comment"), value=absent)
    res = annotate_axiom(
        path=populated_db,
        axiom_hash=target_hash[:8],
        changes=(RemoveAnnotation(remove=absent_ann),),
    )
    assert "+0 added, 0 removed" in res
    assert "1 absent" in res


def test_undeclared_entity_selection_reads_back_present(empty_db):
    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Wolf"), super_class=IRI("ex:Animal")),
        ],
    )
    search_entities(
        path=empty_db,
        into=EntitySelectionName("entities:undeclared"),
        declared=False,
    )
    page = read_selection(path=empty_db, name=EntitySelectionName("entities:undeclared"))
    assert "0 missing" in page
    assert "ex:Wolf" in page
    assert "*missing*" not in page


def test_bcp47_lang_validation_error_message():
    from ontoloom.owl.literals import LangLiteral
    from ontoloom_mcp.components.errors import _format_validation_error
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        LangLiteral(value="x", lang="invalid lang!")
    msg = _format_validation_error(exc_info.value)
    assert "BCP 47" in msg
    assert '"invalid lang!"' in msg


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
        wrapped(
            path=populated_db,
            name=EntitySelectionName("entities:nonexistent"),
        )
    msg = str(exc_info.value)
    assert "nonexistent" in msg
    assert "search_entities" in msg or "match_axioms" in msg


def test_remove_axioms_stale_selection_translates(populated_db):
    # Create an axiom selection, then try to use a wrong hash prefix on it.
    from ontoloom.selections.expr import AxiomsForExpr
    from ontoloom.selections.types import AxiomSelectionName
    from ontoloom_mcp.components.locking import LockedAxiomSelectionName
    from ontoloom_mcp.tools.axioms.remove_axioms import BySelection
    from ontoloom_mcp.tools.selections.create_selection import create_selection

    search_entities(
        path=populated_db,
        into=EntitySelectionName("entities:dogs_ent"),
        query="Dog",
    )
    create_selection(
        path=populated_db,
        name=AxiomSelectionName("axioms:dogs_ax"),
        expr=AxiomsForExpr(axioms_for=SelectionName("dogs_ent")),
    )
    stale = LockedAxiomSelectionName("axioms:dogs_ax@deadbeef")

    wrapped = translate_errors(remove_axioms)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=populated_db, target=BySelection(selection=stale))
    msg = str(exc_info.value)
    assert "changed" in msg
    assert "Current: dogs_ax@" in msg
    assert "items)" in msg


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
    from ontoloom.connection import session
    from ontoloom.prefixes.store import list_prefixes

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
