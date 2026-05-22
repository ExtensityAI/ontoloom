import pytest
from ontoloom.axioms.mutations import add_axioms
from ontoloom.axioms.types import HashedAxiom
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query.dispatch import run
from ontoloom.selections.compose import create_selection
from ontoloom.selections.expr import (
    AxiomsForExpr,
    DiffExpr,
    EntitiesInExpr,
    IntersectExpr,
    UnionExpr,
)
from ontoloom.selections.store import (
    get_selection,
    remove_selections,
    selection_exists,
    upsert_selection,
)
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.read_entity_selection import ReadEntitySelection
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
    SelectionExprError,
    SelectionKind,
    SelectionKindMismatchError,
    SelectionName,
    ShowFilter,
)


def _ax(name: str) -> AxiomSelectionName:
    return AxiomSelectionName(f"axioms:{name}")


def _ent(name: str) -> EntitySelectionName:
    return EntitySelectionName(f"entities:{name}")


# -- P-03-3: Selection set algebra --


def test_union_commutativity(s):
    upsert_selection(s, SelectionName("a"), SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat"], "test")
    upsert_selection(s, SelectionName("b"), SelectionKind.ENTITIES, ["ex:Cat", "ex:Fish"], "test")

    _r = create_selection(
        s, _ent("u_ab"), UnionExpr(union=(SelectionName("a"), SelectionName("b")))
    )
    hash_ab, card_ab = _r.selection.hash, _r.selection.size
    _r = create_selection(
        s, _ent("u_ba"), UnionExpr(union=(SelectionName("b"), SelectionName("a")))
    )
    hash_ba, card_ba = _r.selection.hash, _r.selection.size

    assert card_ab == 3
    assert card_ba == 3
    assert hash_ab == hash_ba


def test_intersection(s):
    upsert_selection(s, SelectionName("a"), SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat"], "test")
    upsert_selection(s, SelectionName("b"), SelectionKind.ENTITIES, ["ex:Cat", "ex:Fish"], "test")

    card = create_selection(
        s, _ent("inter"), IntersectExpr(intersect=(SelectionName("a"), SelectionName("b")))
    ).selection.size
    assert card == 1

    page = run(s, ReadEntitySelection(selection=_ent("inter")))
    assert [item.iri for item in page.items] == ["ex:Cat"]

    upsert_selection(s, SelectionName("c"), SelectionKind.ENTITIES, ["ex:Fish"], "test")
    card_disjoint = create_selection(
        s, _ent("inter_disjoint"), IntersectExpr(intersect=(SelectionName("a"), SelectionName("c")))
    ).selection.size
    assert card_disjoint == 0


def test_difference(s):
    upsert_selection(
        s, SelectionName("a"), SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat", "ex:Fish"], "test"
    )
    upsert_selection(s, SelectionName("b"), SelectionKind.ENTITIES, ["ex:Cat"], "test")

    card_a_minus_b = create_selection(
        s, _ent("diff_ab"), DiffExpr(diff=(SelectionName("a"), SelectionName("b")))
    ).selection.size
    assert card_a_minus_b == 2

    page = run(s, ReadEntitySelection(selection=_ent("diff_ab")))
    assert {item.iri for item in page.items} == {"ex:Dog", "ex:Fish"}

    card_b_minus_a = create_selection(
        s, _ent("diff_ba"), DiffExpr(diff=(SelectionName("b"), SelectionName("a")))
    ).selection.size
    assert card_b_minus_a == 0


def test_axioms_for(s):
    ax1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    add_axioms(s, [ax1, ax2])

    upsert_selection(s, SelectionName("ents"), SelectionKind.ENTITIES, ["ex:Dog"], "test")
    card = create_selection(
        s, _ax("ax_for_dog"), AxiomsForExpr(axioms_for=SelectionName("ents"))
    ).selection.size

    meta = get_selection(s, SelectionName("ax_for_dog"))
    assert meta.kind == SelectionKind.AXIOMS
    assert card == 2


def test_entities_in(s):
    ax = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(s, [ax])
    h = HashedAxiom.of(ax).hash

    upsert_selection(s, SelectionName("axsel"), SelectionKind.AXIOMS, [h], "test")
    _card = create_selection(
        s, _ent("ent_in"), EntitiesInExpr(entities_in=SelectionName("axsel"))
    ).selection.size

    meta = get_selection(s, SelectionName("ent_in"))
    assert meta.kind == SelectionKind.ENTITIES

    page = run(s, ReadEntitySelection(selection=_ent("ent_in")))
    keys = {item.iri for item in page.items}
    assert "ex:Dog" in keys
    assert "ex:Animal" in keys


def test_mixed_kind_raises(s):
    upsert_selection(s, SelectionName("ax_sel"), SelectionKind.AXIOMS, ["a" * 64], "test")
    upsert_selection(s, SelectionName("ent_sel"), SelectionKind.ENTITIES, ["ex:Dog"], "test")

    with pytest.raises(SelectionExprError):
        create_selection(
            s,
            _ent("mixed_union"),
            UnionExpr(union=(SelectionName("ax_sel"), SelectionName("ent_sel"))),
        )


def test_empty_inputs_raises(s):
    with pytest.raises(SelectionExprError):
        create_selection(s, _ent("x"), UnionExpr(union=()))


def test_nested_expression(s):
    """Nested tree: union of axioms_for(ents1) and axioms_for(ents2) in one call."""
    ax1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat"))
    add_axioms(s, [ax1, ax2])

    upsert_selection(s, SelectionName("dogs"), SelectionKind.ENTITIES, ["ex:Dog"], "test")
    upsert_selection(s, SelectionName("cats"), SelectionKind.ENTITIES, ["ex:Cat"], "test")

    expr = UnionExpr(
        union=(
            AxiomsForExpr(axioms_for=SelectionName("dogs")),
            AxiomsForExpr(axioms_for=SelectionName("cats")),
        )
    )
    result = create_selection(s, _ax("all_axs"), expr)
    assert result.selection.kind == SelectionKind.AXIOMS
    assert result.selection.size == 2  # dog SubClassOf + cat Declaration


def test_overwrite_produces_new_hash(s):
    hash1 = upsert_selection(
        s, SelectionName("s"), SelectionKind.ENTITIES, ["ex:Dog"], "test"
    ).selection.hash
    _r = upsert_selection(s, SelectionName("s"), SelectionKind.ENTITIES, ["ex:Cat"], "test")
    hash2, card2 = _r.selection.hash, _r.selection.size

    assert hash2 != hash1
    assert card2 == 1
    assert get_selection(s, SelectionName("s")).size == 1


def test_single_input_intersection_rejected(s):
    upsert_selection(s, SelectionName("a"), SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat"], "test")
    with pytest.raises(SelectionExprError, match="at least two"):
        create_selection(s, _ent("r"), IntersectExpr(intersect=(SelectionName("a"),)))


def test_single_input_difference_rejected(s):
    upsert_selection(s, SelectionName("a"), SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat"], "test")
    with pytest.raises(SelectionExprError, match="at least two"):
        create_selection(s, _ent("r"), DiffExpr(diff=(SelectionName("a"),)))


def test_single_input_union_returns_copy(s):
    upsert_selection(s, SelectionName("a"), SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat"], "test")
    card = create_selection(s, _ent("r"), UnionExpr(union=(SelectionName("a"),))).selection.size
    assert card == 2


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
    upsert_selection(s, SelectionName("sel"), SelectionKind.AXIOMS, [real_hash, fake_hash], "test")

    page_present = run(s, ReadAxiomSelection(selection=_ax("sel"), show=ShowFilter.PRESENT))
    assert all(not item.missing for item in page_present.items)

    page_missing = run(s, ReadAxiomSelection(selection=_ax("sel"), show=ShowFilter.MISSING))
    assert all(item.missing for item in page_missing.items)

    page_all = run(s, ReadAxiomSelection(selection=_ax("sel"), show=ShowFilter.ALL))
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
    upsert_selection(s, SelectionName("s"), SelectionKind.ENTITIES, ["ex:X", "ex:Ghost"], "test")
    page = run(s, ReadEntitySelection(selection=_ent("s")))
    assert page.present + page.missing == page.meta.size
    assert page.present == 1  # ex:X is declared (punned, but COUNT(DISTINCT) = 1)
    assert page.missing == 1  # ex:Ghost has no Declaration


# -- P-03-9: selection hash round-trip --


def test_selection_hash_round_trip(s):
    # Write items in arbitrary order. Read them back and re-write (in the order
    # they came back). The content hash must be stable across both writes because
    # _selection_hash sorts internally.
    items = ["ex:C", "ex:A", "ex:B"]
    result1 = upsert_selection(s, SelectionName("s"), SelectionKind.ENTITIES, items, "test")
    page = run(s, ReadEntitySelection(selection=_ent("s")))
    read_back = [item.iri for item in page.items]
    result2 = upsert_selection(s, SelectionName("s2"), SelectionKind.ENTITIES, read_back, "test")
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


def test_set_operand_validates_bare_string():
    from ontoloom.selections.expr import SetOperand
    from pydantic import TypeAdapter

    result = TypeAdapter(SetOperand).validate_python("my_sel")
    assert result == SelectionName("my_sel")


def test_set_expr_json_schema_marks_object_type():
    from ontoloom.selections.expr import SetExpr
    from pydantic import TypeAdapter

    schema = TypeAdapter(SetExpr).json_schema()
    assert schema.get("type") == "object"


# -- Kind-prefix strict matching --


def test_create_selection_raises_when_ref_kind_disagrees_with_expr(s):
    """`axioms:` prefix on a ref whose expr evaluates to entities should fail."""
    upsert_selection(s, SelectionName("ents"), SelectionKind.ENTITIES, ["ex:Dog"], "test")
    with pytest.raises(SelectionKindMismatchError):
        create_selection(s, _ax("wrong"), UnionExpr(union=(SelectionName("ents"),)))


def test_create_selection_does_not_write_on_mismatch(s):
    """Strict check fires before upsert; no selection materializes on mismatch."""
    upsert_selection(s, SelectionName("ents"), SelectionKind.ENTITIES, ["ex:Dog"], "test")
    with pytest.raises(SelectionKindMismatchError):
        create_selection(s, _ax("wrong"), UnionExpr(union=(SelectionName("ents"),)))
    with pytest.raises(Exception):  # noqa: B017
        get_selection(s, SelectionName("wrong"))


def test_remove_selections_raises_on_kind_mismatch(s):
    """`axioms:foo` ref when `foo` is stored as entities should fail loud, no removal."""
    upsert_selection(s, SelectionName("foo"), SelectionKind.ENTITIES, ["ex:Dog"], "test")
    with pytest.raises(SelectionKindMismatchError):
        remove_selections(s, [_ax("foo")])
    assert get_selection(s, SelectionName("foo")).size == 1  # still there


def test_remove_selections_tolerates_missing(s):
    """Missing names still surface in not_found, not as an exception."""
    result = remove_selections(s, [_ent("ghost")])
    assert result.dropped == ()
    assert result.not_found == (SelectionName("ghost"),)


# -- selection_exists helper --


def test_selection_exists_true_when_kind_matches(s):
    upsert_selection(s, SelectionName("foo"), SelectionKind.AXIOMS, [], source="test")

    assert selection_exists(s, SelectionName("foo"), SelectionKind.AXIOMS) is True


def test_selection_exists_false_when_missing(s):
    assert selection_exists(s, SelectionName("nope"), SelectionKind.AXIOMS) is False


def test_selection_exists_false_when_kind_mismatch(s):
    upsert_selection(s, SelectionName("bar"), SelectionKind.ENTITIES, [], source="test")

    assert selection_exists(s, SelectionName("bar"), SelectionKind.AXIOMS) is False
