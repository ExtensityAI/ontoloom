import pytest
from ontoloom.axioms.hashing import AxiomHash
from ontoloom.axioms.mutations import add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query.dispatch import execute
from ontoloom.selections.compose import create_selection_from_expr
from ontoloom.selections.expr import (
    AxiomsForExpr,
    DiffExpr,
    EntitiesInExpr,
    IntersectExpr,
    UnionExpr,
)
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.read_entity_selection import ReadEntitySelection
from ontoloom.selections.store import (
    DroppedSelection,
    axiom_selection_exists,
    entity_selection_exists,
    get_axiom_selection,
    get_entity_selection,
    remove_selections_any,
    upsert_axiom_selection,
    upsert_entity_selection,
)
from ontoloom.selections.types import (
    SelectionExistsError,
    SelectionExprError,
    SelectionKindConflictError,
    SelectionName,
    SelectionNotFoundError,
    ShowFilter,
    WriteMode,
)


def _ax(name: str) -> SelectionName:
    return SelectionName(name)


def _ent(name: str) -> SelectionName:
    return SelectionName(name)


# -- P-03-3: Selection set algebra --


def test_union_commutativity(s):
    upsert_entity_selection(s, SelectionName("a"), ["ex:Dog", "ex:Cat"], "test")
    upsert_entity_selection(s, SelectionName("b"), ["ex:Cat", "ex:Fish"], "test")

    _r = create_selection_from_expr(
        s, SelectionName("u_ab"), UnionExpr(union=(SelectionName("a"), SelectionName("b")))
    )
    hash_ab, card_ab = _r.selection.hash, _r.selection.size
    _r = create_selection_from_expr(
        s, SelectionName("u_ba"), UnionExpr(union=(SelectionName("b"), SelectionName("a")))
    )
    hash_ba, card_ba = _r.selection.hash, _r.selection.size

    assert card_ab == 3
    assert card_ba == 3
    assert hash_ab == hash_ba


def test_intersection(s):
    upsert_entity_selection(s, SelectionName("a"), ["ex:Dog", "ex:Cat"], "test")
    upsert_entity_selection(s, SelectionName("b"), ["ex:Cat", "ex:Fish"], "test")

    card = create_selection_from_expr(
        s, SelectionName("inter"), IntersectExpr(intersect=(SelectionName("a"), SelectionName("b")))
    ).selection.size
    assert card == 1

    page = execute(s, ReadEntitySelection(selection=_ent("inter")))
    assert [item.iri for item in page.items] == ["ex:Cat"]

    upsert_entity_selection(s, SelectionName("c"), ["ex:Fish"], "test")
    card_disjoint = create_selection_from_expr(
        s,
        SelectionName("inter_disjoint"),
        IntersectExpr(intersect=(SelectionName("a"), SelectionName("c"))),
    ).selection.size
    assert card_disjoint == 0


def test_difference(s):
    upsert_entity_selection(s, SelectionName("a"), ["ex:Dog", "ex:Cat", "ex:Fish"], "test")
    upsert_entity_selection(s, SelectionName("b"), ["ex:Cat"], "test")

    card_a_minus_b = create_selection_from_expr(
        s, SelectionName("diff_ab"), DiffExpr(diff=(SelectionName("a"), SelectionName("b")))
    ).selection.size
    assert card_a_minus_b == 2

    page = execute(s, ReadEntitySelection(selection=_ent("diff_ab")))
    assert {item.iri for item in page.items} == {"ex:Dog", "ex:Fish"}

    card_b_minus_a = create_selection_from_expr(
        s, SelectionName("diff_ba"), DiffExpr(diff=(SelectionName("b"), SelectionName("a")))
    ).selection.size
    assert card_b_minus_a == 0


def test_axioms_for(s):
    ax1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [ax1, ax2])

    upsert_entity_selection(s, SelectionName("ents"), ["ex:Dog"], "test")
    card = create_selection_from_expr(
        s, SelectionName("ax_for_dog"), AxiomsForExpr(axioms_for=SelectionName("ents"))
    ).selection.size

    # Round-trips through the axiom-side store; absence on the entity side proves the kind.
    assert axiom_selection_exists(s, SelectionName("ax_for_dog"))
    assert not entity_selection_exists(s, SelectionName("ax_for_dog"))
    assert card == 2


def test_entities_in(s):
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(s, [ax])
    h = HashedAxiom.of(ax).hash

    upsert_axiom_selection(s, SelectionName("axsel"), [h], "test")
    _card = create_selection_from_expr(
        s, SelectionName("ent_in"), EntitiesInExpr(entities_in=SelectionName("axsel"))
    ).selection.size

    assert entity_selection_exists(s, SelectionName("ent_in"))
    assert not axiom_selection_exists(s, SelectionName("ent_in"))

    page = execute(s, ReadEntitySelection(selection=_ent("ent_in")))
    keys = {item.iri for item in page.items}
    assert "ex:Dog" in keys
    assert "ex:Animal" in keys


def test_empty_inputs_raises(s):
    with pytest.raises(SelectionExprError):
        create_selection_from_expr(s, SelectionName("x"), UnionExpr(union=()))


def test_nested_expression(s):
    """Nested tree: union of axioms_for(ents1) and axioms_for(ents2) in one call."""
    ax1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat"))
    add_axioms(s, [ax1, ax2])

    upsert_entity_selection(s, SelectionName("dogs"), ["ex:Dog"], "test")
    upsert_entity_selection(s, SelectionName("cats"), ["ex:Cat"], "test")

    expr = UnionExpr(
        union=(
            AxiomsForExpr(axioms_for=SelectionName("dogs")),
            AxiomsForExpr(axioms_for=SelectionName("cats")),
        )
    )
    result = create_selection_from_expr(s, SelectionName("all_axs"), expr)
    assert axiom_selection_exists(s, SelectionName("all_axs"))
    assert result.selection.size == 2  # dog SubClassOf + cat Declaration


def test_overwrite_produces_new_hash(s):
    hash1 = upsert_entity_selection(s, SelectionName("s"), ["ex:Dog"], "test").selection.hash
    _r = upsert_entity_selection(s, SelectionName("s"), ["ex:Cat"], "test", mode=WriteMode.REPLACE)
    hash2, card2 = _r.selection.hash, _r.selection.size

    assert hash2 != hash1
    assert card2 == 1
    assert get_entity_selection(s, SelectionName("s")).size == 1


def test_single_input_intersection_rejected(s):
    upsert_entity_selection(s, SelectionName("a"), ["ex:Dog", "ex:Cat"], "test")
    with pytest.raises(SelectionExprError, match="at least two"):
        create_selection_from_expr(
            s, SelectionName("r"), IntersectExpr(intersect=(SelectionName("a"),))
        )


def test_single_input_difference_rejected(s):
    upsert_entity_selection(s, SelectionName("a"), ["ex:Dog", "ex:Cat"], "test")
    with pytest.raises(SelectionExprError, match="at least two"):
        create_selection_from_expr(s, SelectionName("r"), DiffExpr(diff=(SelectionName("a"),)))


def test_single_input_union_returns_copy(s):
    upsert_entity_selection(s, SelectionName("a"), ["ex:Dog", "ex:Cat"], "test")
    card = create_selection_from_expr(
        s, SelectionName("r"), UnionExpr(union=(SelectionName("a"),))
    ).selection.size
    assert card == 2


def test_same_bare_name_forbidden_across_kinds(s):
    """A bare name is unique across kinds: claiming `foo` as an axiom selection
    forbids reusing it as an entity selection (and vice versa)."""
    upsert_axiom_selection(s, SelectionName("foo"), ["a" * 64, "b" * 64], "test")

    with pytest.raises(SelectionKindConflictError):
        upsert_entity_selection(s, SelectionName("foo"), ["ex:Dog"], "test")


# -- P-03-8: Selection validation and boundary cases --


def test_validate_selection_name_empty():
    with pytest.raises(ValueError):
        SelectionName("")


def test_selection_name_rejects_any_at_suffix():
    """Core SelectionName is strict and rejects any `@hash` suffix.

    Lenient stripping is the MCP boundary's job — see
    `packages/mcp/.../tools/test_selection_name_strips_locked_hash_suffix`.
    """
    with pytest.raises(ValueError):
        SelectionName("my_sel@a3f1b2c4")


def test_validate_selection_name_too_long():
    with pytest.raises(ValueError):
        SelectionName("a" * 65)


@pytest.mark.parametrize(
    "bad",
    [
        "foo bar",  # whitespace
        "foo\tbar",  # tab
        "foo\nbar",  # newline
        "foo\x00bar",  # control
        "1abc",  # leading digit
        "_abc",  # leading underscore
        "-abc",  # leading dash
        ".abc",  # leading dot
        "/abc",  # leading slash
        ":abc",  # leading colon
        "foo+bar",  # plus
        "foo*bar",  # star
        "café",  # non-ASCII
    ],
)
def test_selection_name_rejects_disallowed_shapes(bad):
    with pytest.raises(ValueError, match="must start with a letter"):
        SelectionName(bad)


@pytest.mark.parametrize(
    "good",
    [
        "a",
        "my_sel",
        "Candidates_v2",
        "ax-2026",
        "X9",
        "ns:dogs",  # colon (e.g. namespace-style)
        "v1.0",  # dot (e.g. version-style)
        "snomed/concepts",  # slash (e.g. path-style)
        "ex:Dogs.v2-rc1",  # mixed
    ],
)
def test_selection_name_accepts_valid_shapes(good):
    assert SelectionName(good) == good


def test_read_with_show_filters(s):
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(s, [ax])
    real_hash = HashedAxiom.of(ax).hash

    fake_hash = "d" * 64
    upsert_axiom_selection(s, SelectionName("sel"), [real_hash, fake_hash], "test")

    page_present = execute(s, ReadAxiomSelection(selection=_ax("sel"), show=ShowFilter.PRESENT))
    assert all(not item.missing for item in page_present.items)

    page_missing = execute(s, ReadAxiomSelection(selection=_ax("sel"), show=ShowFilter.MISSING))
    assert all(item.missing for item in page_missing.items)

    page_all = execute(s, ReadAxiomSelection(selection=_ax("sel"), show=ShowFilter.ALL))
    assert len(page_all.items) == 2


# -- P-03-8: punned entity present+missing invariant --


def test_read_entities_selection_punned_entity_present_missing_sum(s):
    # OWL punning: :X declared as both CLASS and NAMED_INDIVIDUAL (two Declaration axioms).
    # Entity selection containing :X must satisfy present + missing == cardinality.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:X")),
            Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI("ex:X")),
        ],
    )
    # :ex:Ghost has no Declaration -> should be counted as missing.
    upsert_entity_selection(s, SelectionName("s"), ["ex:X", "ex:Ghost"], "test")
    page = execute(s, ReadEntitySelection(selection=_ent("s")))
    assert page.present + page.missing == page.meta.size
    assert page.present == 1  # ex:X is declared (punned, but COUNT(DISTINCT) = 1)
    assert page.missing == 1  # ex:Ghost has no Declaration


# -- P-03-9: selection hash round-trip --


def test_selection_hash_round_trip(s):
    # Write items in arbitrary order. Read them back and re-write (in the order
    # they came back). The content hash must be stable across both writes because
    # _selection_hash sorts internally.
    items = ["ex:C", "ex:A", "ex:B"]
    result1 = upsert_entity_selection(s, SelectionName("s"), items, "test")
    page = execute(s, ReadEntitySelection(selection=_ent("s")))
    read_back = [item.iri for item in page.items]
    result2 = upsert_entity_selection(s, SelectionName("s2"), read_back, "test")
    assert result1.selection.hash == result2.selection.hash


# -- SetExpr validation from raw dicts (MCP transport path) --


def test_set_expr_validates_union_dict():
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter

    result = TypeAdapter(SetExpr).validate_python({"union": ["a", "b"]})
    assert isinstance(result, UnionExpr)
    assert result.union == (SelectionName("a"), SelectionName("b"))


def test_set_expr_validates_intersect_dict():
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter

    result = TypeAdapter(SetExpr).validate_python({"intersect": ["a", "b"]})
    assert isinstance(result, IntersectExpr)


def test_set_expr_validates_diff_dict():
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter

    result = TypeAdapter(SetExpr).validate_python({"diff": ["a", "b"]})
    assert isinstance(result, DiffExpr)


def test_set_expr_validates_axioms_for_dict():
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter

    result = TypeAdapter(SetExpr).validate_python({"axioms_for": "ents"})
    assert isinstance(result, AxiomsForExpr)
    assert result.axioms_for == SelectionName("ents")


def test_set_expr_validates_entities_in_dict_with_position():
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter

    result = TypeAdapter(SetExpr).validate_python({"entities_in": "axs", "position": "sub_class"})
    assert isinstance(result, EntitiesInExpr)
    assert result.entities_in == SelectionName("axs")


def test_set_expr_validates_nested_compose():
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter

    result = TypeAdapter(SetExpr).validate_python(
        {"union": [{"axioms_for": "a"}, {"axioms_for": "b"}]}
    )
    assert isinstance(result, UnionExpr)
    assert all(isinstance(o, AxiomsForExpr) for o in result.union)


def test_set_expr_validates_bare_string_leaf():
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter

    result = TypeAdapter(SetExpr).validate_python("my_sel")
    assert result == SelectionName("my_sel")


def test_set_expr_rejects_leaf_with_whitespace():
    """Leaf names reject whitespace (and other invalid characters)."""
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter, ValidationError

    with pytest.raises(ValidationError):
        TypeAdapter(SetExpr).validate_python("entities:my sel")


def test_set_expr_accepts_colon_prefixed_leaf_as_bare_name():
    """`:` is a valid name character, so a `kind:`-style string with no space
    now parses as a plain bare name leaf — kind is no longer encoded in the wire form."""
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter

    result = TypeAdapter(SetExpr).validate_python("entities:foo")
    assert result == SelectionName("entities:foo")


def test_set_expr_json_schema_marks_object_type():
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter

    schema = TypeAdapter(SetExpr).json_schema()
    assert schema.get("type") == ["string", "object"]


def test_create_selection_mixed_kind_union_rejected(s):
    """'a' is an axiom selection, 'e' is an entity selection; the union must fail at eval time."""
    upsert_axiom_selection(s, SelectionName("a"), ["a" * 64], "test")
    upsert_entity_selection(s, SelectionName("e"), ["ex:Dog"], "test")

    with pytest.raises(SelectionExprError):
        create_selection_from_expr(
            s,
            SelectionName("mix"),
            UnionExpr(union=(SelectionName("a"), SelectionName("e"))),
            mode=WriteMode.CREATE,
        )


# -- remove_selections_any kind-agnostic sweep --


def test_remove_selections_any_drops_entity_side(s):
    """`remove_selections_any` resolves kind by lookup and drops an entity-side name."""
    upsert_entity_selection(s, SelectionName("foo"), ["ex:Dog"], "test")
    result = remove_selections_any(s, [_ent("foo")])
    assert result.dropped == (DroppedSelection(name=SelectionName("foo"), size=1),)
    assert result.not_found == ()
    assert not entity_selection_exists(s, SelectionName("foo"))


def test_remove_selections_any_drops_axiom_side(s):
    """`remove_selections_any` drops an axiom-side name."""
    upsert_axiom_selection(s, SelectionName("foo"), [AxiomHash("a" * 64)], "test")
    result = remove_selections_any(s, [_ax("foo")])
    assert result.dropped == (DroppedSelection(name=SelectionName("foo"), size=1),)
    assert result.not_found == ()
    assert not axiom_selection_exists(s, SelectionName("foo"))


def test_remove_selections_any_tolerates_missing(s):
    """Missing names still surface in not_found, not as an exception."""
    result = remove_selections_any(s, [_ent("ghost")])
    assert result.dropped == ()
    assert result.not_found == (SelectionName("ghost"),)


# -- compose surfaces SelectionNotFoundError for missing leaves --


def test_create_selection_raises_when_leaf_missing(s):
    """Strict check fires before upsert; no selection materializes."""
    with pytest.raises(SelectionNotFoundError):
        create_selection_from_expr(
            s, SelectionName("wrong"), UnionExpr(union=(SelectionName("ghost"),))
        )


# -- selection_exists helpers --


def test_axiom_selection_exists_true(s):
    upsert_axiom_selection(s, SelectionName("foo"), [], source="test")

    assert axiom_selection_exists(s, SelectionName("foo")) is True


def test_axiom_selection_exists_false_when_missing(s):
    assert axiom_selection_exists(s, SelectionName("nope")) is False


def test_axiom_selection_exists_false_when_only_entity_side(s):
    upsert_entity_selection(s, SelectionName("bar"), [], source="test")

    assert axiom_selection_exists(s, SelectionName("bar")) is False


# -- WriteMode / SelectionExistsError --


def test_write_mode_from_value():
    assert WriteMode("create") is WriteMode.CREATE
    assert WriteMode("replace") is WriteMode.REPLACE


def test_write_mode_rejects_unknown_value():
    with pytest.raises(ValueError):
        WriteMode("union")


def test_selection_exists_error_stringifies_name_and_size():
    err = SelectionExistsError(SelectionName("x"), 3)
    text = str(err)
    assert "x" in text
    assert "3" in text
    assert err.name == "x"
    assert err.existing_size == 3


# -- WriteMode gating on the core write path --


def test_upsert_axiom_create_refuses_existing(s):
    upsert_axiom_selection(s, SelectionName("dup"), ["a" * 64, "b" * 64], "test")

    with pytest.raises(SelectionExistsError) as exc_info:
        upsert_axiom_selection(s, SelectionName("dup"), ["c" * 64], "test", mode=WriteMode.CREATE)

    assert exc_info.value.existing_size == 2
    # Original is untouched.
    assert get_axiom_selection(s, SelectionName("dup")).size == 2


def test_upsert_axiom_replace_overwrites(s):
    upsert_axiom_selection(s, SelectionName("dup"), ["a" * 64, "b" * 64], "test")

    result = upsert_axiom_selection(
        s, SelectionName("dup"), ["c" * 64], "test", mode=WriteMode.REPLACE
    )

    assert result.selection.size == 1
    assert result.previous_size == 2
    assert get_axiom_selection(s, SelectionName("dup")).size == 1


def test_upsert_axiom_create_on_fresh_name_succeeds(s):
    result = upsert_axiom_selection(
        s, SelectionName("fresh"), ["a" * 64], "test", mode=WriteMode.CREATE
    )

    assert result.selection.size == 1
    assert result.previous_size is None


def test_upsert_entity_create_refuses_existing(s):
    upsert_entity_selection(s, SelectionName("dup"), ["ex:Dog"], "test")

    with pytest.raises(SelectionExistsError) as exc_info:
        upsert_entity_selection(s, SelectionName("dup"), ["ex:Cat"], "test", mode=WriteMode.CREATE)

    assert exc_info.value.existing_size == 1
    assert get_entity_selection(s, SelectionName("dup")).size == 1


def test_create_selection_create_refuses_existing(s):
    upsert_axiom_selection(s, SelectionName("occupied"), ["a" * 64], "test")

    with pytest.raises(SelectionExistsError):
        create_selection_from_expr(
            s,
            SelectionName("occupied"),
            UnionExpr(union=(SelectionName("occupied"),)),
            mode=WriteMode.CREATE,
        )


def test_create_refuses_name_taken_by_other_kind(s):
    from ontoloom.selections.store import upsert_axiom_selection, upsert_entity_selection
    from ontoloom.selections.types import SelectionKindConflictError, SelectionName

    upsert_axiom_selection(s, SelectionName("shared"), [AxiomHash("a" * 64)], "t")

    with pytest.raises(SelectionKindConflictError):
        upsert_entity_selection(s, SelectionName("shared"), [IRI("ex:Dog")], "t")
