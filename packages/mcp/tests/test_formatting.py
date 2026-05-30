"""Golden-string tests for the shared formatting vocabulary helpers."""

from ontoloom.axioms.hashing import AxiomHash, short_hash
from ontoloom.axioms.types import HashedAxiom
from ontoloom.owl.axioms import SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.selections.types import (
    AxiomSelection,
    EntitySelection,
    SelectionContentHash,
    SelectionKind,
    SelectionName,
)
from ontoloom_mcp.components.formatting import (
    Ref,
    RenameSource,
    SetExprSource,
    ToolFilterSource,
    _format_axiom_line,
    format_drift,
    format_entity_line,
    format_kinded_count,
    format_list_row,
    format_missing_axiom_line,
    format_overwrite_note,
    format_pagination,
    format_read_header,
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
