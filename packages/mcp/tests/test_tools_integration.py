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
from ontoloom.selections.types import SelectionName
from ontoloom_mcp.components.confirmation import ConfirmationRequiredError
from ontoloom_mcp.components.errors import translate_errors
from ontoloom_mcp.tools.axioms.add_axioms import add_axioms
from ontoloom_mcp.tools.axioms.remove_axioms import remove_axioms
from ontoloom_mcp.tools.axioms.rename_iri import rename_iri
from ontoloom_mcp.tools.entities.get_entity import get_entity
from ontoloom_mcp.tools.entities.search_entities import search_entities
from ontoloom_mcp.tools.ontology.create_ontology import create_ontology
from ontoloom_mcp.tools.prefixes.set_prefix import set_prefix
from ontoloom_mcp.tools.selections.create_selection import create_selection
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
    assert result.startswith("Added 1 axiom, skipped 0 axioms.\n\n```diff\n")
    assert "+" in result


def test_add_axioms_summary_singular_skipped(empty_db):
    dog = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    cat = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat"))
    add_axioms(path=empty_db, axioms=[dog])
    result = add_axioms(path=empty_db, axioms=[cat, dog])
    assert result.startswith("Added 1 axiom, skipped 1 axiom.\n\n```diff\n")


def test_add_axioms_summary_plural_both(empty_db):
    result = add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Bird")),
        ],
    )
    assert result.startswith("Added 3 axioms, skipped 0 axioms.\n\n```diff\n")


def test_add_axioms_summary_all_duplicates(empty_db):
    dog = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    cat = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat"))
    add_axioms(path=empty_db, axioms=[dog, cat])
    result = add_axioms(path=empty_db, axioms=[dog, cat])
    assert result.startswith("Added 0 axioms, skipped 2 axioms.\n\n```diff\n")


def test_get_entity_returns_info(populated_db):
    result = get_entity(path=populated_db, iri=IRI("ex:Dog"))
    # Header is roles-then-label form; no label set so just `iri (roles)`.
    assert result.startswith("ex:Dog (Class)\n")
    assert "Axioms (asserted): 2" in result
    assert "1 Declaration" in result
    assert "1 SubClassOf" in result
    # No into= -> no trailing saved line.
    assert "Saved" not in result


def test_get_entity_with_into_appends_saved_line(populated_db):
    result = get_entity(
        path=populated_db,
        iri=IRI("ex:Dog"),
        into=SelectionName("dog_axioms"),
    )
    # Inspect block at the top.
    assert result.startswith("ex:Dog (Class)\n")
    assert "Axioms (asserted): 2" in result
    # Saved line at the bottom, bare name (no `axioms:` prefix).
    assert result.endswith('Saved 2 axioms to "dog_axioms".')
    assert "axioms:dog_axioms" not in result
    # Source persisted on the selection.
    from ontoloom.selections.store import get_axiom_selection

    with session(Ontology(populated_db)) as s:
        meta = get_axiom_selection(s, SelectionName("dog_axioms"))
        s.commit()
    assert meta.source == 'get_entity(iri="ex:Dog")'


def test_get_entity_with_into_replace_notes_overwrite(populated_db):
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom.selections.store import upsert_axiom_selection
    from ontoloom.selections.types import WriteMode

    # Seed a selection with three distinct placeholder hashes so the overwrite tail fires.
    decoys = [
        HashedAxiom.of(Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A"))).hash,
        HashedAxiom.of(Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B"))).hash,
        HashedAxiom.of(Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C"))).hash,
    ]
    with session(Ontology(populated_db)) as s:
        upsert_axiom_selection(s, SelectionName("dog_axioms"), decoys, "fixture")
        s.commit()

    result = get_entity(
        path=populated_db,
        iri=IRI("ex:Dog"),
        into=SelectionName("dog_axioms"),
        mode=WriteMode.REPLACE,
    )
    assert result.endswith('Saved 2 axioms to "dog_axioms". Replaced previous (3 items).')


def test_get_entity_with_into_zero_axioms_still_renders_inspect(populated_db):
    # Build a within-scope that contains an unrelated axiom so ex:Dog has zero
    # in-scope axioms. The entity still exists globally, so get_entity returns
    # successfully and the inspect block renders with `Axioms (asserted): 0`.
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom.selections.store import upsert_axiom_selection

    unrelated = HashedAxiom.of(Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal"))).hash
    with session(Ontology(populated_db)) as s:
        upsert_axiom_selection(s, SelectionName("animal_only"), [unrelated], "fixture")
        s.commit()

    result = get_entity(
        path=populated_db,
        iri=IRI("ex:Dog"),
        into=SelectionName("empty_dog"),
        within=SelectionName("animal_only"),
    )
    # Inspect block still renders.
    assert result.startswith("ex:Dog (Class)\n")
    assert "Axioms (asserted): 0" in result
    # Saved 0 tail, no "No matches" sentence.
    assert result.endswith('Saved 0 axioms to "empty_dog".')
    assert "No matches" not in result


def test_get_entity_with_label_renders_label_after_roles(populated_db):
    from ontoloom.owl.axioms import AnnotationAssertion

    add_axioms(
        path=populated_db,
        axioms=[
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Dog"),
                value=LangLiteral(value="Dog"),
            )
        ],
    )
    result = get_entity(path=populated_db, iri=IRI("ex:Dog"))
    # Roles before label.
    assert result.startswith('ex:Dog (Class) "Dog"\n')
    assert "Annotations:" in result
    assert 'rdfs:label "Dog"' in result


def test_get_entity_within_persists_source_with_within_suffix(populated_db):
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom.selections.store import get_axiom_selection, upsert_axiom_selection

    dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    dog_hash = HashedAxiom.of(dog_decl).hash
    with session(Ontology(populated_db)) as s:
        upsert_axiom_selection(s, SelectionName("scope_ax"), [dog_hash], "fixture")
        s.commit()

    get_entity(
        path=populated_db,
        iri=IRI("ex:Dog"),
        into=SelectionName("scoped_dog"),
        within=SelectionName("scope_ax"),
    )
    with session(Ontology(populated_db)) as s:
        meta = get_axiom_selection(s, SelectionName("scoped_dog"))
        s.commit()
    assert meta.source == 'get_entity(iri="ex:Dog") within "scope_ax"'


def test_search_entities_creates_selection(populated_db):
    result = search_entities(
        path=populated_db,
        into=SelectionName("dogs"),
        query="Dog",
    )
    # Bare selection name in the saved-line; no `entities:` wire prefix surfaces.
    assert result.startswith('Saved 1 entity to "dogs".\n\n')
    assert "entities:dogs" not in result
    assert "ex:Dog" in result
    # No "Showing 1-N of N entities:" header in the write-block preview.
    assert "Showing" not in result


def test_search_entities_no_results_renders_source(populated_db):
    result = search_entities(
        path=populated_db,
        into=SelectionName("empty_search"),
        query="zzzznomatch",
    )
    assert result == (
        'Saved 0 entities to "empty_search". '
        'No entities found (search_entities(query="zzzznomatch")).'
    )


def test_search_entities_source_includes_role_and_within(populated_db):
    # Build an axiom selection to scope into; check that role + within render in
    # the persisted source string and surface in no_results messages.
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom.owl.axioms import Declaration as _Declaration
    from ontoloom.selections.store import get_entity_selection, upsert_axiom_selection

    dog_decl = _Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    dog_hash = HashedAxiom.of(dog_decl).hash
    with session(Ontology(populated_db)) as s:
        upsert_axiom_selection(s, SelectionName("scope_ax"), [dog_hash], "test fixture")
        s.commit()

    result = search_entities(
        path=populated_db,
        into=SelectionName("scoped"),
        role=EntityType.CLASS,
        within=SelectionName("scope_ax"),
    )
    # No separate "Within selection" footer; within surfaces only via the source.
    assert "Within selection" not in result
    assert result.startswith('Saved 1 entity to "scoped".')

    # Persisted source carries the rendered descriptor.
    with session(Ontology(populated_db)) as s:
        meta = get_entity_selection(s, SelectionName("scoped"))
        s.commit()
    assert meta.source == 'search_entities(role="Class") within "scope_ax"'


def test_create_selection_renders_write_block_with_preview(empty_db):
    from ontoloom.selections.store import upsert_entity_selection

    iris = [IRI(f"ex:E{i}") for i in range(25)]
    add_axioms(
        path=empty_db,
        axioms=[Declaration(entity_type=EntityType.CLASS, iri=iri) for iri in iris],
    )

    with session(Ontology(empty_db)) as s:
        upsert_entity_selection(s, SelectionName("source"), iris, "test fixture")
        s.commit()

    result = create_selection(
        path=empty_db,
        name=SelectionName("derived"),
        expr=SelectionName("source"),
    )
    # Saved line: bare name, no `entities:` prefix; preview body follows after a blank line.
    assert result.startswith('Saved 25 entities to "derived".\n\n')
    assert "entities:derived" not in result
    # First entity row appears in the preview body (with role from declaration).
    assert "ex:E0 (Class)" in result
    # Preview is capped at PREVIEW_ROWS=10; footer points back to read_selection
    # with the bare name and notes the remaining count.
    assert '... and 15 more. Use `read_selection` with "derived" to see all 25.' in result


def test_create_selection_replace_notes_overwrite(empty_db):
    from ontoloom.selections.store import upsert_entity_selection
    from ontoloom.selections.types import WriteMode

    add_axioms(
        path=empty_db,
        axioms=[Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A"))],
    )
    with session(Ontology(empty_db)) as s:
        upsert_entity_selection(s, SelectionName("source"), [IRI("ex:A")], "test fixture")
        upsert_entity_selection(s, SelectionName("derived"), [IRI("ex:Old")], "test fixture")
        s.commit()

    result = create_selection(
        path=empty_db,
        name=SelectionName("derived"),
        expr=SelectionName("source"),
        mode=WriteMode.REPLACE,
    )
    # New saved-line shape: singular "1 entity", bare name, `Replaced previous (N items).` tail.
    assert result.startswith('Saved 1 entity to "derived". Replaced previous (1 items).\n\n')
    assert "entities:derived" not in result
    assert "overwrote previous" not in result
    assert "ex:A (Class)" in result


def test_create_selection_empty_result_renders_clean_saved_line(empty_db):
    from ontoloom.selections.expr import IntersectExpr
    from ontoloom.selections.store import upsert_entity_selection

    with session(Ontology(empty_db)) as s:
        upsert_entity_selection(s, SelectionName("a"), [IRI("ex:A")], "test fixture")
        upsert_entity_selection(s, SelectionName("b"), [IRI("ex:B")], "test fixture")
        s.commit()

    result = create_selection(
        path=empty_db,
        name=SelectionName("empty_result"),
        expr=IntersectExpr(intersect=(SelectionName("a"), SelectionName("b"))),
    )
    # Empty form: saved line ends cleanly with a period, no trailing space, no preview body.
    assert result == 'Saved 0 entities to "empty_result".'


def test_read_selection_after_search(populated_db):
    search_entities(
        path=populated_db,
        into=SelectionName("dogs"),
        query="Dog",
    )
    result = read_selection(path=populated_db, name=SelectionName("dogs"))
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
        into=SelectionName("todos"),
        query="TODO",
    )

    assert 'Saved 1 axiom to "todos".' in result
    assert "axioms:todos" not in result
    assert "SubClassOf" in result

    page = read_selection(path=empty_db, name=SelectionName("todos"))
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
        into=SelectionName("defined"),
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
        into=SelectionName("hits"),
        query="TODO",
        within=SelectionName("scope"),
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
        into=SelectionName("ranked"),
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
        into=SelectionName("empty"),
        query="nonexistent",
    )

    assert result == (
        'Saved 0 axioms to "empty". No matches for search_axioms(query="nonexistent").'
    )


def test_search_axioms_requires_query_or_properties(empty_db):
    from ontoloom_mcp.tools.axioms.search_axioms import search_axioms

    wrapped = translate_errors(search_axioms)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=empty_db, into=SelectionName("x"))
    assert str(exc_info.value) == "search_axioms requires at least one of `query` or `properties`."


def test_match_axioms_saves_matches_with_unified_output(empty_db):
    from ontoloom.patterns.types import SubClassOfPattern
    from ontoloom_mcp.tools.axioms.match_axioms import match_axioms

    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Animal")),
        ],
    )

    result = match_axioms(
        path=empty_db,
        pattern=SubClassOfPattern(sub_class="?x", super_class="?y"),
        into=SelectionName("subclass_animal"),
    )

    assert result.startswith('Saved 2 axioms to "subclass_animal".\n\n')
    assert "axioms:subclass_animal" not in result
    assert "axioms matched" not in result
    assert "SubClassOf(ex:Dog, ex:Animal)" in result
    assert "SubClassOf(ex:Cat, ex:Animal)" in result


def test_match_axioms_truncation_folds_into_saved_line(empty_db):
    from ontoloom.patterns.types import SubClassOfPattern
    from ontoloom_mcp.tools.axioms.match_axioms import match_axioms

    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
            SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Animal")),
        ],
    )

    result = match_axioms(
        path=empty_db,
        pattern=SubClassOfPattern(sub_class="?x", super_class="?y"),
        into=SelectionName("limited"),
        limit=1,
    )

    assert result.startswith(
        'Saved 1 axiom to "limited" (truncated at limit=1; raise it to see more).\n\n'
    )
    assert "SubClassOf" in result


def test_match_axioms_no_results_message(empty_db):
    from ontoloom.patterns.types import SubClassOfPattern
    from ontoloom_mcp.tools.axioms.match_axioms import match_axioms

    add_axioms(
        path=empty_db,
        axioms=[Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))],
    )

    result = match_axioms(
        path=empty_db,
        pattern=SubClassOfPattern(sub_class="?x", super_class="?y"),
        into=SelectionName("no_matches"),
    )

    assert result == 'Saved 0 axioms to "no_matches". No matches for match_axioms.'


def test_match_axioms_no_results_within_scope_renders_within_suffix(empty_db):
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom.patterns.types import SubClassOfPattern
    from ontoloom.selections.store import upsert_axiom_selection
    from ontoloom_mcp.tools.axioms.match_axioms import match_axioms

    decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(path=empty_db, axioms=[decl])

    decl_hash = HashedAxiom.of(decl).hash
    with session(Ontology(empty_db)) as s:
        upsert_axiom_selection(s, SelectionName("scope"), [decl_hash], "test fixture")
        s.commit()

    result = match_axioms(
        path=empty_db,
        pattern=SubClassOfPattern(sub_class="?x", super_class="?y"),
        into=SelectionName("no_matches"),
        within=SelectionName("scope"),
    )

    assert result == 'Saved 0 axioms to "no_matches". No matches for match_axioms within "scope".'


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
            into=SelectionName("dups"),
            annotation_property=IRI("rdfs:label"),
            within=SelectionName("nonexistent"),
        )
    msg = str(exc_info.value)
    assert "nonexistent" in msg
    assert "search_entities" in msg or "match_axioms" in msg


def test_find_duplicate_entities_no_duplicates_still_writes_selection(populated_db):
    from ontoloom.selections.store import get_entity_selection
    from ontoloom_mcp.tools.entities.find_duplicate_entities import find_duplicate_entities

    # populated_db has no duplicate rdfs:label values.
    result = find_duplicate_entities(
        path=populated_db,
        into=SelectionName("dup_labels"),
        annotation_property=IRI("rdfs:label"),
    )
    assert result == (
        'Saved 0 entities to "dup_labels". '
        'No duplicates for find_duplicate_entities(annotation_property="rdfs:label").'
    )
    # Selection actually exists in the store after the call.
    with session(Ontology(populated_db)) as s:
        meta = get_entity_selection(s, SelectionName("dup_labels"))
        s.commit()
    assert meta.size == 0


def test_find_duplicate_entities_no_duplicates_within_renders_scope(empty_db):
    from ontoloom.owl.axioms import AnnotationAssertion
    from ontoloom_mcp.tools.entities.find_duplicate_entities import find_duplicate_entities

    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
            AnnotationAssertion(
                property=IRI("rdfs:label"), subject=IRI("ex:A"), value=LangLiteral(value="alpha")
            ),
        ],
    )
    search_entities(path=empty_db, into=SelectionName("scope"), namespace=PrefixName("ex"))

    result = find_duplicate_entities(
        path=empty_db,
        into=SelectionName("dup_labels"),
        annotation_property=IRI("rdfs:label"),
        within=SelectionName("scope"),
    )
    assert result == (
        'Saved 0 entities to "dup_labels". '
        'No duplicates for find_duplicate_entities(annotation_property="rdfs:label") '
        'within "scope".'
    )


def test_find_duplicate_entities_groups_render_with_saved_line(empty_db):
    from ontoloom.owl.axioms import AnnotationAssertion
    from ontoloom_mcp.tools.entities.find_duplicate_entities import find_duplicate_entities

    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Canine")),
            AnnotationAssertion(
                property=IRI("rdfs:label"), subject=IRI("ex:Dog"), value=LangLiteral(value="Dog")
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Canine"),
                value=LangLiteral(value="Dog"),
            ),
        ],
    )

    result = find_duplicate_entities(
        path=empty_db,
        into=SelectionName("dup_labels"),
        annotation_property=IRI("rdfs:label"),
    )
    assert result.startswith('Saved 2 entities to "dup_labels". ')
    assert "1 duplicate rdfs:label values:" in result
    # No leading "Found N ... across M ..." prose.
    assert "Found " not in result
    assert "across " not in result
    # No selection-ref arrow form.
    assert "entities:dup_labels" not in result
    # Group line format: 2-space indent, value, kind-counted entity count, IRIs
    # (iris are ordered by the underlying SQL, alphabetical within a group).
    assert '  "Dog" (2 entities): ex:Canine, ex:Dog' in result


def test_find_duplicate_entities_overwrite_notes_replacement(empty_db):
    from ontoloom.owl.axioms import AnnotationAssertion
    from ontoloom.selections.types import WriteMode
    from ontoloom_mcp.tools.entities.find_duplicate_entities import find_duplicate_entities

    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Canine")),
            AnnotationAssertion(
                property=IRI("rdfs:label"), subject=IRI("ex:Dog"), value=LangLiteral(value="Dog")
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Canine"),
                value=LangLiteral(value="Dog"),
            ),
        ],
    )

    find_duplicate_entities(
        path=empty_db,
        into=SelectionName("dup_labels"),
        annotation_property=IRI("rdfs:label"),
    )
    result = find_duplicate_entities(
        path=empty_db,
        into=SelectionName("dup_labels"),
        annotation_property=IRI("rdfs:label"),
        mode=WriteMode.REPLACE,
    )
    # Overwrite tail sits between the saved-line period and the domain clause.
    assert result.startswith(
        'Saved 2 entities to "dup_labels". Replaced previous (2 items). '
        "1 duplicate rdfs:label values:"
    )


def test_find_duplicate_entities_group_overflow_renders_more_line(empty_db):
    from ontoloom.owl.axioms import AnnotationAssertion
    from ontoloom_mcp.tools.entities.find_duplicate_entities import find_duplicate_entities

    axioms = []
    # 11 duplicate-value groups -> overflow at 10.
    for i in range(11):
        a = IRI(f"ex:E{i}a")
        b = IRI(f"ex:E{i}b")
        axioms.extend(
            [
                Declaration(entity_type=EntityType.CLASS, iri=a),
                Declaration(entity_type=EntityType.CLASS, iri=b),
                AnnotationAssertion(
                    property=IRI("rdfs:label"), subject=a, value=LangLiteral(value=f"label{i}")
                ),
                AnnotationAssertion(
                    property=IRI("rdfs:label"), subject=b, value=LangLiteral(value=f"label{i}")
                ),
            ]
        )
    add_axioms(path=empty_db, axioms=axioms)

    result = find_duplicate_entities(
        path=empty_db,
        into=SelectionName("dup_labels"),
        annotation_property=IRI("rdfs:label"),
    )
    assert result.startswith('Saved 22 entities to "dup_labels". 11 duplicate rdfs:label values:')
    # First 10 groups are listed; the 11th is the overflow.
    assert result.count('" (2 entities): ') == 10
    assert "... and 1 more." in result
    # No legacy "more groups" wording.
    assert "more groups." not in result


def test_find_duplicate_entities_singular_entity_pluralization(empty_db):
    """Group with a single IRI (impossible in normal flow) would render `(1 entity)`.

    The N=2 case (`(2 entities)`) is covered above; this test pins the
    pluralization branch so the helper choice (`format_kinded_count`) stays
    locked in and a regression to a hardcoded ` entities)` would fail.
    """
    from ontoloom.owl.axioms import AnnotationAssertion
    from ontoloom_mcp.tools.entities.find_duplicate_entities import find_duplicate_entities

    add_axioms(
        path=empty_db,
        axioms=[
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Canine")),
            AnnotationAssertion(
                property=IRI("rdfs:label"), subject=IRI("ex:Dog"), value=LangLiteral(value="Dog")
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Canine"),
                value=LangLiteral(value="Dog"),
            ),
        ],
    )
    result = find_duplicate_entities(
        path=empty_db,
        into=SelectionName("dup_labels"),
        annotation_property=IRI("rdfs:label"),
    )
    # The plural branch is hit (2 entities); verify the exact spelling so a regression
    # to a hand-rolled ` entities)` suffix would still pass but `(2 entities)` is locked.
    assert "(2 entities)" in result
    assert "(2 entity)" not in result


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
        into=SelectionName("undeclared"),
        declared=False,
    )
    page = read_selection(path=empty_db, name=SelectionName("undeclared"))
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
            name=SelectionName("nonexistent"),
        )
    msg = str(exc_info.value)
    assert "nonexistent" in msg
    assert "search_entities" in msg or "match_axioms" in msg


def _make_dogs_selection(path):
    """Create axiom-selection 'axioms:dogs_ax' over the ex:Dog axioms."""
    from ontoloom.selections.expr import AxiomsForExpr
    from ontoloom_mcp.tools.selections.create_selection import create_selection

    search_entities(path=path, into=SelectionName("dogs_ent"), query="Dog")
    create_selection(
        path=path,
        name=SelectionName("dogs_ax"),
        expr=AxiomsForExpr(axioms_for=SelectionName("dogs_ent")),
    )


def _count_axioms(path):
    from ontoloom.query.dispatch import execute
    from ontoloom.query.list_axioms import ListAxioms

    ont = Ontology(path)
    with session(ont) as s:
        count = len(execute(s, ListAxioms(constraints=())))
        s.commit()
    return count


def test_remove_axioms_by_selection_first_call_previews_and_requires_confirm(populated_db):
    from ontoloom_mcp.tools.axioms.remove_axioms import BySelection

    _make_dogs_selection(populated_db)
    before = _count_axioms(populated_db)

    with pytest.raises(ConfirmationRequiredError) as exc_info:
        remove_axioms(path=populated_db, target=BySelection(name=SelectionName("dogs_ax")))

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

    target = BySelection(name=SelectionName("dogs_ax"))
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
    target = BySelection(name=SelectionName("dogs_ax"))

    with pytest.raises(ConfirmationRequiredError) as exc_info:
        remove_axioms(path=populated_db, target=target)
    old_token = exc_info.value.token

    # Overwrite the selection's contents (now the ex:Animal axioms instead).
    search_entities(path=populated_db, into=SelectionName("animals_ent"), query="Animal")
    create_selection(
        path=populated_db,
        name=SelectionName("dogs_ax"),
        expr=AxiomsForExpr(axioms_for=SelectionName("animals_ent")),
        mode=WriteMode.REPLACE,
    )

    # The old token no longer matches the recomputed one -> fresh preview.
    with pytest.raises(ConfirmationRequiredError) as exc_info2:
        remove_axioms(path=populated_db, target=target, confirm=old_token)
    assert exc_info2.value.token != old_token


def test_remove_axioms_by_hashes_removes_without_confirmation(populated_db):
    from ontoloom.query.dispatch import execute
    from ontoloom.query.list_axioms import ListAxioms
    from ontoloom_mcp.tools.axioms.remove_axioms import ByHashes

    ont = Ontology(populated_db)
    with session(ont) as s:
        first_hash = execute(s, ListAxioms(constraints=()))[0][0]
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


def test_rename_iri_no_collision_renders_diff_with_summary(populated_db):
    from ontoloom.axioms.hashing import short_hash
    from ontoloom.axioms.types import HashedAxiom

    new_dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Puppy"))
    new_sub = SubClassOf(sub_class=IRI("ex:Puppy"), super_class=IRI("ex:Animal"))
    old_dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    old_sub = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    old_dog_h = HashedAxiom.of(old_dog_decl).hash
    old_sub_h = HashedAxiom.of(old_sub).hash
    new_dog_h = HashedAxiom.of(new_dog_decl).hash
    new_sub_h = HashedAxiom.of(new_sub).hash

    result = rename_iri(path=populated_db, old_iri=IRI("ex:Dog"), new_iri=IRI("ex:Puppy"))

    expected = (
        "Renamed ex:Dog -> ex:Puppy: 2 axioms replaced.\n\n"
        "```diff\n"
        f"- [{short_hash(old_sub_h)}] {old_sub}\n"
        f"+ [{short_hash(new_sub_h)}] {new_sub}\n"
        f"- [{short_hash(old_dog_h)}] {old_dog_decl}\n"
        f"+ [{short_hash(new_dog_h)}] {new_dog_decl}\n"
        "```"
    )
    assert result == expected


def test_rename_iri_no_op_when_iri_absent(populated_db):
    result = rename_iri(path=populated_db, old_iri=IRI("ex:NotPresent"), new_iri=IRI("ex:Other"))
    assert result == "No axioms found mentioning ex:NotPresent. No-op."


def test_rename_iri_into_appends_saved_line(populated_db):
    result = rename_iri(
        path=populated_db,
        old_iri=IRI("ex:Dog"),
        new_iri=IRI("ex:Puppy"),
        into=SelectionName("renamed_dog"),
    )
    # Body is the summary + diff; saved line trails after a blank line.
    assert result.startswith("Renamed ex:Dog -> ex:Puppy: 2 axioms replaced.\n\n```diff\n")
    assert result.endswith('\n```\n\nSaved 2 axioms to "renamed_dog".')


def test_rename_iri_within_persists_source_with_within_suffix(populated_db):
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom.selections.store import (
        get_axiom_selection,
        upsert_axiom_selection,
    )

    dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    dog_decl_hash = HashedAxiom.of(dog_decl).hash

    with session(Ontology(populated_db)) as s:
        upsert_axiom_selection(s, SelectionName("scope"), [dog_decl_hash], "test fixture")
        s.commit()

    rename_iri(
        path=populated_db,
        old_iri=IRI("ex:Dog"),
        new_iri=IRI("ex:Puppy"),
        within=SelectionName("scope"),
        into=SelectionName("renamed_dog"),
    )

    with session(Ontology(populated_db)) as s:
        meta = get_axiom_selection(s, SelectionName("renamed_dog"))
        s.commit()
    assert meta.source == 'rename_iri(ex:Dog -> ex:Puppy) within "scope"'


def test_rename_iri_collision_without_confirm_raises_with_short_hashes(populated_db):
    from ontoloom.axioms.hashing import short_hash
    from ontoloom.axioms.types import HashedAxiom

    # Renaming ex:Dog -> ex:Animal collides on the Declaration axiom.
    new_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal"))
    new_decl_h = HashedAxiom.of(new_decl).hash

    with pytest.raises(ConfirmationRequiredError) as exc_info:
        rename_iri(path=populated_db, old_iri=IRI("ex:Dog"), new_iri=IRI("ex:Animal"))

    msg = str(exc_info.value)
    expected_body = (
        "Renaming ex:Dog -> ex:Animal would merge 1 axiom(s) into existing axioms "
        "(annotations on the merged axioms may be lost). "
        f"Colliding new hashes: [{short_hash(new_decl_h)}]."
    )
    assert msg.startswith(expected_body)
    assert msg.endswith(f'To proceed, call again with confirm="{exc_info.value.token}".')
    # No raw AxiomHash(...) repr leaked into the message.
    assert "AxiomHash(" not in msg


def test_rename_iri_collision_with_correct_token_renders_merge_note(populated_db):
    with pytest.raises(ConfirmationRequiredError) as exc_info:
        rename_iri(path=populated_db, old_iri=IRI("ex:Dog"), new_iri=IRI("ex:Animal"))
    token = exc_info.value.token

    result = rename_iri(
        path=populated_db,
        old_iri=IRI("ex:Dog"),
        new_iri=IRI("ex:Animal"),
        confirm=token,
    )
    # Two axioms get rewritten: the Declaration collides (merged), the SubClassOf does not.
    assert result.startswith(
        "Renamed ex:Dog -> ex:Animal: 2 axioms replaced. 1 merged into existing axioms.\n\n"
        "```diff\n"
    )
    assert result.endswith("\n```")


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
        within=SelectionName("scope"),
    )
    assert result.startswith("Renamed ex:Dog -> ex:Puppy: 1 axioms replaced.\n\n```diff\n")

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
            within=SelectionName("scope"),
        )
    token = exc_info.value.token

    result = rename_iri(
        path=populated_db,
        old_iri=IRI("ex:Dog"),
        new_iri=IRI("ex:Animal"),
        within=SelectionName("scope"),
        confirm=token,
    )
    assert "1 merged into existing axioms." in result


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
            within=SelectionName("scope"),
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
            within=SelectionName("scope"),
        )
    token_after = second.value.token

    assert token_before != token_after


def test_replace_axiom_no_op_when_new_hashes_to_old(populated_db):
    from ontoloom.axioms.hashing import short_hash
    from ontoloom.axioms.types import HashedAxiom
    from ontoloom_mcp.tools.axioms.replace_axiom import replace_axiom

    sub = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    sub_h = HashedAxiom.of(sub).hash

    result = replace_axiom(
        path=populated_db,
        axiom_hash=AxiomHashPrefix(short_hash(sub_h)),
        new_axiom=sub,
    )

    assert result == f"No-op: new axiom has same hash as old [{short_hash(sub_h)}]."


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

    first = search_axioms(path=empty_db, into=SelectionName("t"), query="dog")
    assert 'Saved 1 axiom to "t".' in first
    assert "axioms:t" not in first

    wrapped = translate_errors(search_axioms)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=empty_db, into=SelectionName("t"), query="dog")
    msg = str(exc_info.value)
    assert "already exists" in msg
    assert 'mode="replace"' in msg

    overwrote = search_axioms(
        path=empty_db,
        into=SelectionName("t"),
        query="dog",
        mode=WriteMode.REPLACE,
    )
    assert 'Saved 1 axiom to "t".' in overwrote
    assert "Replaced previous (1 items)." in overwrote
    assert "axioms:t" not in overwrote


def test_search_entities_create_refuses_then_replace_overwrites(populated_db):
    from ontoloom.selections.types import WriteMode

    search_entities(path=populated_db, into=SelectionName("t"), query="Dog")

    wrapped = translate_errors(search_entities)
    with pytest.raises(ToolError) as exc_info:
        wrapped(path=populated_db, into=SelectionName("t"), query="Dog")
    msg = str(exc_info.value)
    assert "already exists" in msg
    assert 'mode="replace"' in msg

    overwrote = search_entities(
        path=populated_db,
        into=SelectionName("t"),
        query="Dog",
        mode=WriteMode.REPLACE,
    )
    assert 'Saved 1 entity to "t".' in overwrote
    assert "Replaced previous (1 items)." in overwrote
    assert "entities:t" not in overwrote


def test_producer_tools_accept_mode_argument(populated_db):
    """Light smoke test: each producer accepts a `mode` kwarg without error."""
    # Give two entities a shared label so find_duplicate_entities produces a selection.
    from ontoloom.owl.axioms import AnnotationAssertion
    from ontoloom.patterns.types import SubClassOfPattern
    from ontoloom.selections.expr import UnionExpr
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
        into=SelectionName("m"),
        mode=WriteMode.CREATE,
    )
    get_entity(
        path=populated_db,
        iri=IRI("ex:Dog"),
        into=SelectionName("ge"),
        mode=WriteMode.CREATE,
    )
    find_duplicate_entities(
        path=populated_db,
        into=SelectionName("dup"),
        annotation_property=IRI("rdfs:label"),
        mode=WriteMode.CREATE,
    )
    create_selection(
        path=populated_db,
        name=SelectionName("composed"),
        expr=UnionExpr(union=(SelectionName("m"),)),
        mode=WriteMode.CREATE,
    )
