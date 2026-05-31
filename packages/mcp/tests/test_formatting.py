"""Golden-string tests for the shared formatting vocabulary helpers."""

import pytest
from ontoloom.axioms.hashing import AxiomHash, short_hash
from ontoloom.axioms.mutations import add_axioms as core_add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Ontology, session
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import AnnotationAssertion, Declaration, SubClassOf
from ontoloom.owl.iri import IRI, RDFS_LABEL
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.store import set_prefix
from ontoloom.prefixes.types import NamespaceIRI, PrefixName
from ontoloom.selections.store import (
    AxiomUpsertResult,
    EntityUpsertResult,
    upsert_axiom_selection,
    upsert_entity_selection,
)
from ontoloom.selections.types import (
    AxiomSelection,
    EntitySelection,
    SelectionContentHash,
    SelectionKind,
    SelectionName,
)
from ontoloom_mcp.components.formatting import (
    PREVIEW_ROWS,
    AxiomPreviewData,
    EntityPreviewData,
    Ref,
    RenameSource,
    SetExprSource,
    ToolFilterSource,
    _format_axiom_line,
    fetch_preview_data,
    format_axiom_blocks,
    format_drift,
    format_entity_line,
    format_kinded_count,
    format_list_row,
    format_missing_axiom_line,
    format_overwrite_note,
    format_pagination,
    format_read_header,
    format_saved_line,
    format_selection_write,
    format_source,
    format_within_scope,
)


def _axiom_sel(name: str, size: int) -> AxiomSelection:
    return AxiomSelection(
        name=SelectionName(name),
        hash=SelectionContentHash("0123456789abcdef"),
        size=size,
    )


def _entity_sel(name: str, size: int) -> EntitySelection:
    return EntitySelection(
        name=SelectionName(name),
        hash=SelectionContentHash("0123456789abcdef"),
        size=size,
    )


def _axiom_upserted(name: str, size: int, previous_size: int | None = None) -> AxiomUpsertResult:
    return AxiomUpsertResult(selection=_axiom_sel(name, size), previous_size=previous_size)


def _entity_upserted(name: str, size: int, previous_size: int | None = None) -> EntityUpsertResult:
    return EntityUpsertResult(selection=_entity_sel(name, size), previous_size=previous_size)


def test_kinded_count_axioms_singular():
    assert format_kinded_count(SelectionKind.AXIOMS, 1) == "1 axiom"


def test_kinded_count_axioms_plural():
    assert format_kinded_count(SelectionKind.AXIOMS, 2) == "2 axioms"


def test_kinded_count_axioms_zero():
    assert format_kinded_count(SelectionKind.AXIOMS, 0) == "0 axioms"


def test_kinded_count_entities_singular():
    assert format_kinded_count(SelectionKind.ENTITIES, 1) == "1 entity"


def test_kinded_count_entities_plural():
    assert format_kinded_count(SelectionKind.ENTITIES, 12) == "12 entities"


def test_kinded_count_entities_zero():
    assert format_kinded_count(SelectionKind.ENTITIES, 0) == "0 entities"


def test_drift_populated():
    assert format_drift(3, 2) == "3 present, 2 missing"


def test_drift_no_missing_is_empty():
    assert format_drift(5, 0) == ""


def test_overwrite_note_populated_has_leading_space_and_period():
    assert format_overwrite_note(3) == " Replaced previous (3 items)."


def test_overwrite_note_none_is_empty():
    assert format_overwrite_note(None) == ""


def test_overwrite_note_concatenates_directly():
    base = 'Saved 2 axioms to "x".'
    assert base + format_overwrite_note(3) == 'Saved 2 axioms to "x". Replaced previous (3 items).'


def test_axiom_line_present_with_label_hint_unchanged():
    ha = HashedAxiom.of(SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")))
    refs = (Ref(iri=IRI("ex:Dog"), label="Dog"),)
    assert _format_axiom_line(ha, refs) == (
        f'[{short_hash(ha.hash)}] SubClassOf(ex:Dog, ex:Animal)  # ex:Dog "Dog"'
    )


def test_missing_axiom_line_renders_bracketed_short_hash():
    full = AxiomHash("a1b2c3d4e5f6" + "0" * 52)
    assert format_missing_axiom_line(full) == "[a1b2c3d4e5f6] *missing*"


def test_axiom_blocks_one_entry_per_axiom():
    h1 = HashedAxiom.of(SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")))
    h2 = HashedAxiom.of(SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Animal")))
    blocks = format_axiom_blocks([h1, h2])
    assert blocks == [
        f"[{short_hash(h1.hash)}] SubClassOf(ex:Dog, ex:Animal)",
        f"[{short_hash(h2.hash)}] SubClassOf(ex:Cat, ex:Animal)",
    ]


def test_axiom_blocks_annotation_continuations_stay_grouped():
    annotated = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(Annotation(property=RDFS_LABEL, value=LangLiteral(value="note")),),
    )
    h1 = HashedAxiom.of(annotated)
    h2 = HashedAxiom.of(SubClassOf(sub_class=IRI("ex:Cat"), super_class=IRI("ex:Animal")))
    blocks = format_axiom_blocks([h1, h2])
    # Two axioms in -> two blocks out, even though h1 spans two lines.
    assert len(blocks) == 2
    # The annotation continuation is part of h1's single block, not a sibling entry.
    assert "\n" in blocks[0]
    head1, cont1 = blocks[0].split("\n", 1)
    assert head1 == f"[{short_hash(h1.hash)}] {annotated}"
    assert cont1.startswith("  # ")
    assert "\n" not in blocks[1]


def test_axiom_blocks_empty_returns_empty_list():
    assert format_axiom_blocks([]) == []


def test_entity_line_label_and_multiple_roles():
    ref = Ref(iri=IRI("ex:Dog"), label="Dog")
    roles = frozenset({EntityType.CLASS, EntityType.OBJECT_PROPERTY})
    assert format_entity_line(ref, roles) == 'ex:Dog (Class, ObjectProperty) "Dog"'


def test_entity_line_no_label_with_role():
    ref = Ref(iri=IRI("ex:Tail"), label=None)
    roles = frozenset({EntityType.CLASS})
    assert format_entity_line(ref, roles) == "ex:Tail (Class)"


def test_entity_line_label_no_roles():
    ref = Ref(iri=IRI("ex:Dog"), label="Dog")
    assert format_entity_line(ref, frozenset()) == 'ex:Dog "Dog"'


def test_entity_line_no_label_no_roles():
    ref = Ref(iri=IRI("ex:Dog"), label=None)
    assert format_entity_line(ref, frozenset()) == "ex:Dog"


def test_pagination_empty_page_axioms_no_filter():
    assert format_pagination(0, 0, 0, SelectionKind.AXIOMS) == "0 axioms."


def test_pagination_empty_page_axioms_with_filter():
    assert (
        format_pagination(0, 0, 0, SelectionKind.AXIOMS, filter="present")
        == "0 axioms (filter: present)."
    )


def test_pagination_empty_page_entities_no_filter():
    assert format_pagination(0, 0, 0, SelectionKind.ENTITIES) == "0 entities."


def test_pagination_empty_when_x_greater_than_y():
    assert format_pagination(5, 4, 10, SelectionKind.AXIOMS) == "0 axioms."


def test_pagination_range_entities_no_filter():
    assert format_pagination(1, 6, 6, SelectionKind.ENTITIES) == "Showing 1-6 of 6 entities:"


def test_pagination_range_axioms_with_filter():
    assert (
        format_pagination(1, 3, 3, SelectionKind.AXIOMS, filter="all")
        == "Showing 1-3 of 3 axioms (filter: all):"
    )


def test_pagination_range_axioms_singular_total():
    # z=1 should still pluralize correctly via format_kinded_count
    assert format_pagination(1, 1, 1, SelectionKind.AXIOMS) == "Showing 1-1 of 1 axiom:"


def test_read_header_axioms_no_missing_still_shows_drift():
    meta = _axiom_sel("subclass_animal", 2)
    assert (
        format_read_header(meta, present=2, missing=0)
        == '"subclass_animal": 2 axioms - 2 present, 0 missing'
    )


def test_read_header_axioms_singular_total_all_missing():
    meta = _axiom_sel("review", 1)
    assert (
        format_read_header(meta, present=0, missing=1) == '"review": 1 axiom - 0 present, 1 missing'
    )


def test_read_header_entities():
    meta = _entity_sel("all_classes", 6)
    assert (
        format_read_header(meta, present=6, missing=0)
        == '"all_classes": 6 entities - 6 present, 0 missing'
    )


def test_list_row_axioms_no_drift():
    meta = _axiom_sel("subclass_animal", 2)
    assert (
        format_list_row(meta, present=2, missing=0, source="match_axioms")
        == '  "subclass_animal": 2 axioms - source: match_axioms'
    )


def test_list_row_axioms_with_drift():
    meta = _axiom_sel("review", 1)
    assert (
        format_list_row(meta, present=0, missing=1, source='search_axioms(query="review")')
        == '  "review": 1 axiom, 1 missing - source: search_axioms(query="review")'
    )


def test_list_row_entities_no_drift():
    meta = _entity_sel("all_classes", 6)
    assert (
        format_list_row(meta, present=6, missing=0, source='search_entities(role="Class")')
        == '  "all_classes": 6 entities - source: search_entities(role="Class")'
    )


def test_within_scope_axioms():
    meta = _axiom_sel("dogs", 7)
    assert format_within_scope(meta) == 'Within "dogs" (7 axioms)'


def test_within_scope_entities():
    meta = _entity_sel("all_classes", 12)
    assert format_within_scope(meta) == 'Within "all_classes" (12 entities)'


def test_within_scope_singular_axiom():
    meta = _axiom_sel("only_one", 1)
    assert format_within_scope(meta) == 'Within "only_one" (1 axiom)'


def test_source_tool_no_filters_bare_name():
    assert format_source(ToolFilterSource("match_axioms", {})) == "match_axioms"


def test_source_tool_quoted_string_filter():
    assert (
        format_source(ToolFilterSource("search_axioms", {"query": "x"}))
        == 'search_axioms(query="x")'
    )


def test_source_tool_mixed_string_and_bool_filters():
    assert (
        format_source(ToolFilterSource("search_entities", {"role": "Class", "declared": True}))
        == 'search_entities(role="Class", declared=True)'
    )


def test_source_tool_list_of_strings_filter():
    assert (
        format_source(ToolFilterSource("search_axioms", {"properties": ["rdfs:comment"]}))
        == 'search_axioms(properties=["rdfs:comment"])'
    )


def test_source_rename_uses_ascii_arrow():
    assert format_source(RenameSource("ex:Cat", "ex:Dog")) == "rename_iri(ex:Cat -> ex:Dog)"


def test_source_set_expr_verbatim():
    assert (
        format_source(SetExprSource("union(all_classes, dog_search)"))
        == "union(all_classes, dog_search)"
    )


def test_source_tool_with_filters_within_suffix():
    assert (
        format_source(ToolFilterSource("search_entities", {"role": "Class"}, within="dogs"))
        == 'search_entities(role="Class") within "dogs"'
    )


def test_source_tool_no_filters_within_suffix():
    assert (
        format_source(ToolFilterSource("match_axioms", {}, within="dogs"))
        == 'match_axioms within "dogs"'
    )


def test_source_rename_within_suffix():
    assert (
        format_source(RenameSource("ex:Cat", "ex:Dog", within="scope"))
        == 'rename_iri(ex:Cat -> ex:Dog) within "scope"'
    )


def test_source_set_expr_within_suffix():
    assert (
        format_source(SetExprSource("union(a, b)", within="scope")) == 'union(a, b) within "scope"'
    )


# -- format_saved_line --


def test_saved_line_axioms_plural_no_overwrite():
    assert format_saved_line(_axiom_upserted("x", 2)) == 'Saved 2 axioms to "x".'


def test_saved_line_axioms_singular_no_overwrite():
    assert format_saved_line(_axiom_upserted("x", 1)) == 'Saved 1 axiom to "x".'


def test_saved_line_axioms_with_overwrite():
    assert (
        format_saved_line(_axiom_upserted("x", 2, previous_size=3))
        == 'Saved 2 axioms to "x". Replaced previous (3 items).'
    )


def test_saved_line_axioms_with_truncated_limit():
    assert (
        format_saved_line(_axiom_upserted("limited", 2), truncated_limit=1)
        == 'Saved 2 axioms to "limited" (truncated at limit=1; raise it to see more).'
    )


def test_saved_line_axioms_truncated_and_overwrite():
    assert format_saved_line(_axiom_upserted("limited", 2, previous_size=3), truncated_limit=1) == (
        'Saved 2 axioms to "limited" (truncated at limit=1; raise it to see more).'
        " Replaced previous (3 items)."
    )


def test_saved_line_entities_plural():
    assert format_saved_line(_entity_upserted("dogs", 4)) == 'Saved 4 entities to "dogs".'


def test_saved_line_entities_singular():
    assert format_saved_line(_entity_upserted("dogs", 1)) == 'Saved 1 entity to "dogs".'


# -- format_selection_write --


def test_write_block_empty_uses_no_results():
    out = format_selection_write(
        _axiom_upserted("review", 0),
        no_results='No matches for search_axioms(query="review").',
    )
    assert out == ('Saved 0 axioms to "review". No matches for search_axioms(query="review").')


def test_write_block_nonempty_joins_saved_then_blank_then_preview():
    ha = HashedAxiom.of(SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")))
    preview = AxiomPreviewData(rows=((ha, ()),))
    out = format_selection_write(_axiom_upserted("x", 2), preview)
    assert out == f'Saved 2 axioms to "x".\n\n[{short_hash(ha.hash)}] SubClassOf(ex:Dog, ex:Animal)'


def test_write_block_nonempty_with_overwrite_in_saved_line():
    ha = HashedAxiom.of(SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")))
    preview = AxiomPreviewData(rows=((ha, ()),))
    out = format_selection_write(_axiom_upserted("x", 2, previous_size=3), preview)
    assert out == (
        f'Saved 2 axioms to "x". Replaced previous (3 items).\n\n'
        f"[{short_hash(ha.hash)}] SubClassOf(ex:Dog, ex:Animal)"
    )


def test_write_block_nonempty_with_truncated_limit_passthrough():
    ha = HashedAxiom.of(SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")))
    preview = AxiomPreviewData(rows=((ha, ()),))
    out = format_selection_write(_axiom_upserted("limited", 2), preview, truncated_limit=1)
    assert out == (
        f'Saved 2 axioms to "limited" (truncated at limit=1; raise it to see more).\n\n'
        f"[{short_hash(ha.hash)}] SubClassOf(ex:Dog, ex:Animal)"
    )


def test_write_block_empty_with_no_results_omitted_strips_trailing_space():
    out = format_selection_write(_axiom_upserted("review", 0))
    assert out == 'Saved 0 axioms to "review".'


def test_write_block_entities_renders_entity_lines():
    preview = EntityPreviewData(
        rows=(
            (Ref(iri=IRI("ex:Cat"), label=None), frozenset({EntityType.CLASS})),
            (Ref(iri=IRI("ex:Dog"), label="Dog"), frozenset({EntityType.CLASS})),
        ),
    )
    out = format_selection_write(_entity_upserted("ents", 2), preview)
    assert out == ('Saved 2 entities to "ents".\n\nex:Cat (Class)\nex:Dog (Class) "Dog"')


# -- fetch_preview_data (DB fixtures) --


@pytest.fixture()
def ont(tmp_path):
    path = tmp_path / "preview.ontology.db"
    Ontology.create(path)
    with session(Ontology(path)) as s:
        set_prefix(s, PrefixName("ex"), NamespaceIRI("http://example.org/"))
        s.commit()
    return Ontology(path)


def _label_assertion(iri: IRI, text: str) -> AnnotationAssertion:
    return AnnotationAssertion(property=RDFS_LABEL, subject=iri, value=LangLiteral(value=text))


def test_preview_axiom_selection_small(ont):
    with session(ont) as s:
        axioms = [Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:C{i}")) for i in range(3)]
        core_add_axioms(s, axioms)
        hashes = [HashedAxiom.of(a).hash for a in axioms]
        upserted = upsert_axiom_selection(s, SelectionName("small"), hashes, "test")
        preview = fetch_preview_data(s, upserted)
        s.commit()
    out = format_selection_write(upserted, preview)

    body = out.split("\n\n", 1)[1]
    lines = body.splitlines()
    assert len(lines) == 3
    for i, line in enumerate(lines):
        assert f"Declaration(Class, ex:C{i})" in line
    assert "more" not in out


def test_preview_axiom_selection_large_appends_footer(ont):
    with session(ont) as s:
        axioms = [
            Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:C{i:02d}")) for i in range(15)
        ]
        core_add_axioms(s, axioms)
        hashes = [HashedAxiom.of(a).hash for a in axioms]
        upserted = upsert_axiom_selection(s, SelectionName("big"), hashes, "test")
        preview = fetch_preview_data(s, upserted)
        s.commit()
    out = format_selection_write(upserted, preview)

    parts = out.split("\n\n")
    # saved-line, body, footer
    assert len(parts) == 3
    row_lines = parts[1].splitlines()
    assert len(row_lines) == PREVIEW_ROWS
    assert parts[2] == ('... and 5 more. Use `read_selection` with "big" to see all 15.')


def test_preview_entity_selection_small(ont):
    with session(ont) as s:
        core_add_axioms(
            s,
            [
                Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
                Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
                _label_assertion(IRI("ex:Dog"), "Dog"),
            ],
        )
        iris = [IRI("ex:Cat"), IRI("ex:Dog")]
        upserted = upsert_entity_selection(s, SelectionName("ents"), iris, "test")
        preview = fetch_preview_data(s, upserted)
        s.commit()
    out = format_selection_write(upserted, preview)

    body = out.split("\n\n", 1)[1]
    lines = body.splitlines()
    assert len(lines) == 2
    # ReadEntitySelection orders by IRI lexicographically: Cat before Dog.
    assert lines[0] == "ex:Cat (Class)"
    assert lines[1] == 'ex:Dog (Class) "Dog"'
    assert "more" not in out


def test_preview_entity_selection_large_appends_footer(ont):
    with session(ont) as s:
        axioms = [
            Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:E{i:02d}")) for i in range(12)
        ]
        core_add_axioms(s, axioms)
        iris = [IRI(f"ex:E{i:02d}") for i in range(12)]
        upserted = upsert_entity_selection(s, SelectionName("ebig"), iris, "test")
        preview = fetch_preview_data(s, upserted)
        s.commit()
    out = format_selection_write(upserted, preview)

    parts = out.split("\n\n")
    # saved-line, body, footer
    assert len(parts) == 3
    row_lines = parts[1].splitlines()
    assert len(row_lines) == PREVIEW_ROWS
    assert parts[2] == ('... and 2 more. Use `read_selection` with "ebig" to see all 12.')
