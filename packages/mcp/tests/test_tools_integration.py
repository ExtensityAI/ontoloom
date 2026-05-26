"""Integration tests for MCP tool functions.

Each test calls a tool function directly (the same callable wrapped by
`create_tool`) to exercise input validation, formatting, and error translation.
"""

import pytest
from fastmcp.exceptions import ToolError
from ontoloom.axioms.hashing import AxiomHashPrefix
from ontoloom.connection import Ontology, session
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.types import NamespaceIRI, PrefixName
from ontoloom.selections.types import AxiomSelectionName, EntitySelectionName, SelectionName
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

EX = PrefixName("ex")
EX_IRI = NamespaceIRI("http://example.org/")
FOO = PrefixName("foo")
FOO_IRI = NamespaceIRI("http://example.org/foo/")
OTHER_EX_IRI = NamespaceIRI("http://other.example.org/")


@pytest.fixture()
def empty_db(tmp_path):
    path = tmp_path / "test.ontology.db"
    Ontology.create(path)
    set_prefix(path=path, name=EX, iri=EX_IRI)
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
    assert '"entities:dogs"' in result
    assert "entities:dogs@" not in result


def test_read_selection_after_search(populated_db):
    search_entities(
        path=populated_db,
        into=EntitySelectionName("entities:dogs"),
        query="Dog",
    )
    result = read_selection(path=populated_db, name=EntitySelectionName("entities:dogs"))
    assert "ex:Dog" in result


def test_search_axioms_by_text(empty_db):
    from ontoloom_mcp.tools.axioms.search_axioms import search_axioms

    todo_comment = Annotation(
        property=IRI("rdfs:comment"),
        value=LangLiteral(value="this is a TODO note"),
    )
    other_comment = Annotation(
        property=IRI("rdfs:comment"),
        value=LangLiteral(value="unrelated content"),
    )
    axiom_a = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(todo_comment,),
    )
    axiom_b = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(other_comment,),
    )
    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            axiom_a,
            axiom_b,
        ],
    )

    result = search_axioms(
        path=empty_db,
        into=AxiomSelectionName("axioms:todos"),
        query="TODO",
    )

    assert '"axioms:todos"' in result
    assert "axioms:todos@" not in result
    assert "1 axioms" in result
    assert "SubClassOf" in result

    page = read_selection(path=empty_db, name=AxiomSelectionName("axioms:todos"))
    assert "ex:Dog" in page
    assert "ex:Cat" not in page
    assert "TODO" in page


def test_search_axioms_by_property_only(empty_db):
    from ontoloom_mcp.tools.axioms.search_axioms import search_axioms

    is_defined_by = Annotation(
        property=IRI("rdfs:isDefinedBy"),
        value=LangLiteral(value="http://example.org/ontology"),
    )
    plain_comment = Annotation(
        property=IRI("rdfs:comment"),
        value=LangLiteral(value="just a comment"),
    )
    defined_axiom = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(is_defined_by,),
    )
    commented_axiom = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(plain_comment,),
    )
    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            defined_axiom,
            commented_axiom,
        ],
    )

    search_axioms(
        path=empty_db,
        into=AxiomSelectionName("axioms:defined"),
        properties=[IRI("rdfs:isDefinedBy")],
    )

    from ontoloom.axioms.types import HashedAxiom

    defined_hash = HashedAxiom.of(defined_axiom).hash
    commented_hash = HashedAxiom.of(commented_axiom).hash

    with session(Ontology(empty_db)) as s:
        rows = s.conn.execute(
            "SELECT item FROM axiom_selection_items WHERE selection_name = ?",
            ("defined",),
        ).fetchall()
        s.commit()
    hashes = {r[0] for r in rows}
    assert defined_hash in hashes
    assert commented_hash not in hashes


def test_search_axioms_with_within_scope(empty_db):
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom.selections.store import upsert_axiom_selection
    from ontoloom_mcp.tools.axioms.search_axioms import search_axioms

    todo = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="TODO"))
    in_scope_todo = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(todo,),
    )
    out_of_scope_todo = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(todo,),
    )
    no_anno = SubClassOf(
        sub_class=IRI("ex:Wolf"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Wolf")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            in_scope_todo,
            out_of_scope_todo,
            no_anno,
        ],
    )

    in_scope_hash = HashedAxiom.of(in_scope_todo).hash
    no_anno_hash = HashedAxiom.of(no_anno).hash
    out_of_scope_hash = HashedAxiom.of(out_of_scope_todo).hash

    # Pre-build a scope selection containing the in-scope TODO and the no-anno axiom,
    # but NOT the out-of-scope TODO.
    with session(Ontology(empty_db)) as s:
        upsert_axiom_selection(
            s,
            SelectionName("scope"),
            [in_scope_hash, no_anno_hash],
            "test fixture",
        )
        s.commit()

    search_axioms(
        path=empty_db,
        into=AxiomSelectionName("axioms:hits"),
        query="TODO",
        within=AxiomSelectionName("axioms:scope"),
    )

    with session(Ontology(empty_db)) as s:
        rows = s.conn.execute(
            "SELECT item FROM axiom_selection_items WHERE selection_name = ?",
            ("hits",),
        ).fetchall()
        s.commit()
    hashes = {r[0] for r in rows}
    assert hashes == {in_scope_hash}
    assert out_of_scope_hash not in hashes
    assert no_anno_hash not in hashes


def test_search_axioms_exact_ranked_before_substring(empty_db):
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom_mcp.tools.axioms.search_axioms import search_axioms

    exact = Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="TODO"))
    substring = Annotation(
        property=IRI("rdfs:comment"),
        value=LangLiteral(value="TODO and more text"),
    )
    axiom_a = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(exact,),
    )
    axiom_b = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(substring,),
    )
    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            axiom_a,
            axiom_b,
        ],
    )

    search_axioms(
        path=empty_db,
        into=AxiomSelectionName("axioms:ranked"),
        query="TODO",
    )

    hash_a = HashedAxiom.of(axiom_a).hash
    hash_b = HashedAxiom.of(axiom_b).hash

    # `read_selection` re-orders by hash, so verify ranking via raw rowid order
    # (insertion order, which `upsert_axiom_selection` preserves from the search's
    # exact-first ranking).
    with session(Ontology(empty_db)) as s:
        rows = s.conn.execute(
            "SELECT item FROM axiom_selection_items WHERE selection_name = ? ORDER BY rowid",
            ("ranked",),
        ).fetchall()
        s.commit()
    ordered = [r[0] for r in rows]
    assert ordered == [hash_a, hash_b]


def test_search_axioms_no_results_message(empty_db):
    from ontoloom_mcp.tools.axioms.search_axioms import search_axioms

    add_axioms(
        path=empty_db,
        axioms=[Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))],
    )

    result = search_axioms(
        path=empty_db,
        into=AxiomSelectionName("axioms:empty"),
        query="nonexistent",
    )

    assert result.startswith("0 axioms ->")
    assert "search_axioms(query=" in result
    assert "No axioms found" in result


def test_search_axioms_requires_query_or_properties(empty_db):
    from ontoloom_mcp.tools.axioms.search_axioms import search_axioms

    with pytest.raises(ValueError, match="search_axioms requires at least one of"):
        search_axioms(path=empty_db, into=AxiomSelectionName("axioms:x"))


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


def test_find_duplicate_entities_within_missing_selection_translates(populated_db):
    from ontoloom_mcp.tools.entities.find_duplicate_entities import find_duplicate_entities

    wrapped = translate_errors(find_duplicate_entities)
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
    from ontoloom.owl.annotations import Annotation
    from ontoloom.owl.literals import LangLiteral
    from ontoloom_mcp.tools.axioms.annotate_axiom import (
        AddAnnotation,
        RemoveAnnotation,
        annotate_axiom,
    )

    note = LangLiteral(value="A subclass relation.")
    add_ann = Annotation(property=IRI("rdfs:comment"), value=note)
    # Find the SubClassOf axiom hash
    from ontoloom.owl.axioms import SubClassOf as _SubClassOf

    sub_axiom = _SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    from ontoloom.axioms.types import HashedAxiom

    target_hash = HashedAxiom.of(sub_axiom).hash

    # Fresh add: +1 added, no skipped
    fresh = annotate_axiom(
        path=populated_db,
        axiom_hash=AxiomHashPrefix(target_hash[:8]),
        changes=(AddAnnotation(add=add_ann),),
    )
    assert "+1 added, 0 removed" in fresh
    assert "already present" not in fresh
    assert "absent" not in fresh

    # Duplicate adds: applied 0 fresh, 1 already present
    dup = annotate_axiom(
        path=populated_db,
        axiom_hash=AxiomHashPrefix(target_hash[:8]),
        changes=(AddAnnotation(add=add_ann), AddAnnotation(add=add_ann)),
    )
    assert "+0 added, 0 removed" in dup
    assert "1 already present" in dup

    # Remove an absent annotation: 0 removed, 1 absent
    absent = LangLiteral(value="not present")
    absent_ann = Annotation(property=IRI("rdfs:comment"), value=absent)
    res = annotate_axiom(
        path=populated_db,
        axiom_hash=AxiomHashPrefix(target_hash[:8]),
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
    from ontoloom_mcp.components.errors import format_error
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        LangLiteral(value="x", lang="invalid lang!")  # pyright: ignore[reportArgumentType]
    msg = format_error(exc_info.value)
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


def _make_dogs_selection(path):
    """Create axiom-selection 'axioms:dogs_ax' over the ex:Dog axioms."""
    from ontoloom.selections.expr import AxiomsForExpr
    from ontoloom_mcp.tools.selections.create_selection import create_selection

    search_entities(path=path, into=EntitySelectionName("entities:dogs_ent"), query="Dog")
    create_selection(
        path=path,
        name=AxiomSelectionName("axioms:dogs_ax"),
        expr=AxiomsForExpr(axioms_for=EntitySelectionName("entities:dogs_ent")),
    )


def _count_axioms(path):
    from ontoloom.query.dispatch import run
    from ontoloom.query.list_axioms import ListAxioms

    ont = Ontology(path)
    with session(ont) as s:
        count = len(run(s, ListAxioms(constraints=())))
        s.commit()
    return count


def test_remove_axioms_by_selection_first_call_previews_and_requires_confirm(populated_db):
    from ontoloom_mcp.tools.axioms.remove_axioms import BySelection

    _make_dogs_selection(populated_db)
    before = _count_axioms(populated_db)

    with pytest.raises(ConfirmationRequiredError) as exc_info:
        remove_axioms(
            path=populated_db, target=BySelection(name=AxiomSelectionName("axioms:dogs_ax"))
        )

    msg = str(exc_info.value)
    assert "Removing" in msg
    # The ex:Dog declaration and the SubClassOf axiom mention Dog -> count of 2.
    assert "Removing 2 axioms" in msg
    assert "ex:Dog" in msg
    assert "confirm=" in msg
    assert exc_info.value.token
    # Nothing removed on the preview call.
    assert _count_axioms(populated_db) == before


def test_remove_axioms_by_selection_confirm_token_removes(populated_db):
    from ontoloom_mcp.tools.axioms.remove_axioms import BySelection

    _make_dogs_selection(populated_db)
    before = _count_axioms(populated_db)

    target = BySelection(name=AxiomSelectionName("axioms:dogs_ax"))
    with pytest.raises(ConfirmationRequiredError) as exc_info:
        remove_axioms(path=populated_db, target=target)
    token = exc_info.value.token

    result = remove_axioms(path=populated_db, target=target, confirm=token)
    assert "Removed 2 axioms" in result
    assert _count_axioms(populated_db) == before - 2


def test_remove_axioms_by_selection_stale_token_re_previews(populated_db):
    from ontoloom.selections.expr import AxiomsForExpr
    from ontoloom.selections.types import WriteMode
    from ontoloom_mcp.tools.axioms.remove_axioms import BySelection
    from ontoloom_mcp.tools.selections.create_selection import create_selection

    _make_dogs_selection(populated_db)
    target = BySelection(name=AxiomSelectionName("axioms:dogs_ax"))

    with pytest.raises(ConfirmationRequiredError) as exc_info:
        remove_axioms(path=populated_db, target=target)
    old_token = exc_info.value.token

    # Overwrite the selection's contents (now the ex:Animal axioms instead).
    search_entities(
        path=populated_db, into=EntitySelectionName("entities:animals_ent"), query="Animal"
    )
    create_selection(
        path=populated_db,
        name=AxiomSelectionName("axioms:dogs_ax"),
        expr=AxiomsForExpr(axioms_for=EntitySelectionName("entities:animals_ent")),
        mode=WriteMode.REPLACE,
    )

    # The old token no longer matches the recomputed one -> fresh preview.
    with pytest.raises(ConfirmationRequiredError) as exc_info2:
        remove_axioms(path=populated_db, target=target, confirm=old_token)
    assert exc_info2.value.token != old_token


def test_remove_axioms_by_hashes_removes_without_confirmation(populated_db):
    from ontoloom.query.dispatch import run
    from ontoloom.query.list_axioms import ListAxioms
    from ontoloom_mcp.tools.axioms.remove_axioms import ByHashes

    ont = Ontology(populated_db)
    with session(ont) as s:
        first_hash = run(s, ListAxioms(constraints=()))[0][0]
        s.commit()
    before = _count_axioms(populated_db)

    result = remove_axioms(
        path=populated_db, target=ByHashes(hashes=(AxiomHashPrefix(first_hash),))
    )
    assert "Removed 1 axioms" in result
    assert _count_axioms(populated_db) == before - 1


def test_axiom_dispatch_failure_renders_focused_mcp_message():
    """A bad axiom dict, validated through the Axiom union adapter, should
    raise UnionDispatchError; the MCP-layer formatter renders it as a focused
    single-line message — not the multi-KB union signature dump."""
    from ontoloom.models import UnionDispatchError
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
    result = set_prefix(
        path=empty_db,
        name=PrefixName("myns"),
        iri=NamespaceIRI("http://example.org/myns/"),
    )
    assert "myns" in result
    assert "http://example.org/myns/" in result


def test_set_prefix_same_iri_returns_unchanged(empty_db):
    set_prefix(path=empty_db, name=FOO, iri=FOO_IRI)
    result = set_prefix(path=empty_db, name=FOO, iri=FOO_IRI)
    assert "(unchanged)" in result


def test_set_prefix_reassign_unused_prefix_no_confirm_required(empty_db):
    # Set a fresh prefix, then reassign before any entity uses it.
    set_prefix(path=empty_db, name=FOO, iri=FOO_IRI)
    result = set_prefix(path=empty_db, name=FOO, iri=NamespaceIRI("http://example.org/foo2/"))
    assert "foo" in result
    assert "http://example.org/foo2/" in result


def test_set_prefix_reassign_in_use_without_confirm_raises(populated_db):
    # populated_db has ex:Dog, ex:Animal, etc. as entities. After registering 'ex'
    # as a prefix mapping, those entities count as "in use" of that prefix.
    set_prefix(path=populated_db, name=EX, iri=EX_IRI)

    with pytest.raises(ConfirmationRequiredError) as exc_info:
        set_prefix(path=populated_db, name=EX, iri=OTHER_EX_IRI)
    assert exc_info.value.token
    assert "confirm=" in str(exc_info.value)


def test_set_prefix_reassign_in_use_with_correct_token_succeeds(populated_db):
    set_prefix(path=populated_db, name=EX, iri=EX_IRI)

    with pytest.raises(ConfirmationRequiredError) as exc_info:
        set_prefix(path=populated_db, name=EX, iri=OTHER_EX_IRI)
    token = exc_info.value.token

    result = set_prefix(
        path=populated_db,
        name=EX,
        iri=OTHER_EX_IRI,
        confirm=token,
    )
    assert "ex" in result
    assert "http://other.example.org/" in result


def test_set_prefix_reassign_in_use_with_wrong_token_raises(populated_db):
    set_prefix(path=populated_db, name=EX, iri=EX_IRI)

    with pytest.raises(ConfirmationRequiredError):
        set_prefix(
            path=populated_db,
            name=EX,
            iri=OTHER_EX_IRI,
            confirm="00000000",
        )
    # State unchanged: ex still maps to its original IRI.
    from ontoloom.connection import session
    from ontoloom.prefixes.store import list_prefixes

    with session(Ontology(populated_db)) as s:
        prefixes = list_prefixes(s)
        s.commit()
    assert prefixes[EX] == "http://example.org/"


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


def test_rename_iri_within_bare_scope_limits_rename(populated_db):
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom.selections.store import upsert_axiom_selection

    dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    dog_decl_hash = HashedAxiom.of(dog_decl).hash

    # Scope holds only the ex:Dog declaration, not the SubClassOf(ex:Dog, ...).
    with session(Ontology(populated_db)) as s:
        upsert_axiom_selection(s, SelectionName("scope"), [dog_decl_hash], "test fixture")
        s.commit()

    result = rename_iri(
        path=populated_db,
        old_iri=IRI("ex:Dog"),
        new_iri=IRI("ex:Puppy"),
        within=AxiomSelectionName("axioms:scope"),
    )
    assert "1 axioms replaced" in result

    # The SubClassOf is out of scope, so it still mentions ex:Dog.
    with session(Ontology(populated_db)) as s:
        subclass_rows = s.conn.execute(
            "SELECT COUNT(*) FROM axiom_entities WHERE entity_iri = ?", ("ex:Dog",)
        ).fetchone()
        s.commit()
    assert subclass_rows[0] == 1  # only the SubClassOf still references ex:Dog


def test_rename_iri_within_scope_collision_token_round_trips(populated_db):
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom.selections.store import upsert_axiom_selection

    dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    dog_decl_hash = HashedAxiom.of(dog_decl).hash

    with session(Ontology(populated_db)) as s:
        upsert_axiom_selection(s, SelectionName("scope"), [dog_decl_hash], "test fixture")
        s.commit()

    # Renaming ex:Dog -> ex:Animal collides on the Declaration axiom.
    with pytest.raises(ConfirmationRequiredError) as exc_info:
        rename_iri(
            path=populated_db,
            old_iri=IRI("ex:Dog"),
            new_iri=IRI("ex:Animal"),
            within=AxiomSelectionName("axioms:scope"),
        )
    token = exc_info.value.token

    result = rename_iri(
        path=populated_db,
        old_iri=IRI("ex:Dog"),
        new_iri=IRI("ex:Animal"),
        within=AxiomSelectionName("axioms:scope"),
        confirm=token,
    )
    assert "merged" in result


def test_rename_iri_within_scope_change_invalidates_token(populated_db):
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom.selections.store import upsert_axiom_selection
    from ontoloom.selections.types import WriteMode

    dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    dog_decl_hash = HashedAxiom.of(dog_decl).hash
    animal_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal"))
    animal_decl_hash = HashedAxiom.of(animal_decl).hash

    with session(Ontology(populated_db)) as s:
        upsert_axiom_selection(s, SelectionName("scope"), [dog_decl_hash], "test fixture")
        s.commit()

    with pytest.raises(ConfirmationRequiredError) as first:
        rename_iri(
            path=populated_db,
            old_iri=IRI("ex:Dog"),
            new_iri=IRI("ex:Animal"),
            within=AxiomSelectionName("axioms:scope"),
        )
    token_before = first.value.token

    # Change the scope's contents (add an extra hash). The rename still collides
    # on the in-scope ex:Dog declaration, but the scope identity has changed.
    with session(Ontology(populated_db)) as s:
        upsert_axiom_selection(
            s,
            SelectionName("scope"),
            [dog_decl_hash, animal_decl_hash],
            "test fixture",
            mode=WriteMode.REPLACE,
        )
        s.commit()

    with pytest.raises(ConfirmationRequiredError) as second:
        rename_iri(
            path=populated_db,
            old_iri=IRI("ex:Dog"),
            new_iri=IRI("ex:Animal"),
            within=AxiomSelectionName("axioms:scope"),
        )
    token_after = second.value.token

    assert token_before != token_after


# -- WriteMode: non-destructive selection writes --


def test_search_axioms_create_refuses_then_replace_overwrites(empty_db):
    from ontoloom.selections.types import WriteMode
    from ontoloom_mcp.tools.axioms.search_axioms import search_axioms

    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(
                entity_type=EntityType.CLASS,
                iri=IRI("ex:Dog"),
                annotations=[
                    Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="a dog"))
                ],
            )
        ],
    )

    first = search_axioms(path=empty_db, into=AxiomSelectionName("axioms:t"), query="dog")
    assert '"axioms:t"' in first
    assert "axioms:t@" not in first

    wrapped = translate_errors(search_axioms)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=empty_db, into=AxiomSelectionName("axioms:t"), query="dog")
    msg = str(exc_info.value)
    assert "already exists" in msg
    assert 'mode="replace"' in msg

    overwrote = search_axioms(
        path=empty_db,
        into=AxiomSelectionName("axioms:t"),
        query="dog",
        mode=WriteMode.REPLACE,
    )
    assert '"axioms:t"' in overwrote
    assert "axioms:t@" not in overwrote


def test_search_entities_create_refuses_then_replace_overwrites(populated_db):
    from ontoloom.selections.types import WriteMode

    search_entities(path=populated_db, into=EntitySelectionName("entities:t"), query="Dog")

    wrapped = translate_errors(search_entities)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=populated_db, into=EntitySelectionName("entities:t"), query="Dog")
    msg = str(exc_info.value)
    assert "already exists" in msg
    assert 'mode="replace"' in msg

    overwrote = search_entities(
        path=populated_db,
        into=EntitySelectionName("entities:t"),
        query="Dog",
        mode=WriteMode.REPLACE,
    )
    assert '"entities:t"' in overwrote
    assert "entities:t@" not in overwrote


def test_producer_tools_accept_mode_argument(populated_db):
    """Light smoke test: each producer accepts a `mode` kwarg without error."""
    # Give two entities a shared label so find_duplicate_entities produces a selection.
    from ontoloom.owl.axioms import AnnotationAssertion
    from ontoloom.patterns.types import SubClassOfPattern
    from ontoloom.selections.expr import AxiomUnionExpr
    from ontoloom.selections.types import WriteMode
    from ontoloom_mcp.tools.axioms.match_axioms import match_axioms
    from ontoloom_mcp.tools.entities.find_duplicate_entities import find_duplicate_entities
    from ontoloom_mcp.tools.selections.create_selection import create_selection

    add_axioms(
        path=populated_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Pup")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Hound")),
            AnnotationAssertion(
                property=IRI("rdfs:label"), subject=IRI("ex:Pup"), value=LangLiteral(value="shared")
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Hound"),
                value=LangLiteral(value="shared"),
            ),
        ],
    )

    match_axioms(
        path=populated_db,
        pattern=SubClassOfPattern(sub_class="?x", super_class="?y"),
        into=AxiomSelectionName("axioms:m"),
        mode=WriteMode.CREATE,
    )
    get_entity(
        path=populated_db,
        iri=IRI("ex:Dog"),
        into=AxiomSelectionName("axioms:ge"),
        mode=WriteMode.CREATE,
    )
    find_duplicate_entities(
        path=populated_db,
        into=EntitySelectionName("entities:dup"),
        annotation_property=IRI("rdfs:label"),
        mode=WriteMode.CREATE,
    )
    create_selection(
        path=populated_db,
        name=AxiomSelectionName("axioms:composed"),
        expr=AxiomUnionExpr(union=(AxiomSelectionName("axioms:m"),)),
        mode=WriteMode.CREATE,
    )
