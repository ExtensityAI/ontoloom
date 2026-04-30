import pytest
from ontoloom.ontology import axioms, selections
from ontoloom.ontology.canonical import axiom_hash
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.errors import BadRequestError, StaleSelectionError
from ontoloom.ontology.models.axioms import Declaration, SubClassOf
from ontoloom.ontology.models.expressions import NamedClass
from ontoloom.ontology.models.literals import IRI, EntityType
from ontoloom.ontology.types import LockedSelection, SelectionKind, ShowFilter, validate_selection_name


@pytest.fixture()
def ont(tmp_path):
    path = tmp_path / "test.ontology.db"
    Ontology.create(path)
    with Ontology(path) as o:
        yield o


# -- P-03-3: Selection set algebra --


def test_union_commutativity(ont):
    selections.upsert(ont, "a", SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat"], "test")
    selections.upsert(ont, "b", SelectionKind.ENTITIES, ["ex:Cat", "ex:Fish"], "test")

    _r = selections.create(ont, "u_ab", union=["a", "b"])
    hash_ab, card_ab = _r.content_hash, _r.cardinality
    _r = selections.create(ont, "u_ba", union=["b", "a"])
    hash_ba, card_ba = _r.content_hash, _r.cardinality

    assert card_ab == 3
    assert card_ba == 3
    assert hash_ab == hash_ba


def test_intersection(ont):
    selections.upsert(ont, "a", SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat"], "test")
    selections.upsert(ont, "b", SelectionKind.ENTITIES, ["ex:Cat", "ex:Fish"], "test")

    card = selections.create(ont, "inter", intersection=["a", "b"]).cardinality
    assert card == 1

    page = selections.read(ont, "inter")
    assert [item.key for item in page.items] == ["ex:Cat"]

    selections.upsert(ont, "c", SelectionKind.ENTITIES, ["ex:Fish"], "test")
    card_disjoint = selections.create(ont, "inter_disjoint", intersection=["a", "c"]).cardinality
    assert card_disjoint == 0


def test_difference(ont):
    selections.upsert(ont, "a", SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat", "ex:Fish"], "test")
    selections.upsert(ont, "b", SelectionKind.ENTITIES, ["ex:Cat"], "test")

    card_a_minus_b = selections.create(ont, "diff_ab", difference=["a", "b"]).cardinality
    assert card_a_minus_b == 2

    page = selections.read(ont, "diff_ab")
    assert {item.key for item in page.items} == {"ex:Dog", "ex:Fish"}

    card_b_minus_a = selections.create(ont, "diff_ba", difference=["b", "a"]).cardinality
    assert card_b_minus_a == 0


def test_axioms_for(ont):
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    axioms.add(ont, [ax1, ax2])

    selections.upsert(ont, "ents", SelectionKind.ENTITIES, ["ex:Dog"], "test")
    card = selections.create(ont, "ax_for_dog", axioms_for="ents").cardinality

    meta = selections.get(ont, "ax_for_dog")
    assert meta.kind == SelectionKind.AXIOMS
    assert card == 2


def test_entities_in(ont):
    ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    axioms.add(ont, [ax])
    h = axiom_hash(ax)

    selections.upsert(ont, "axsel", SelectionKind.AXIOMS, [h], "test")
    _card = selections.create(ont, "ent_in", entities_in="axsel").cardinality

    meta = selections.get(ont, "ent_in")
    assert meta.kind == SelectionKind.ENTITIES

    page = selections.read(ont, "ent_in")
    keys = {item.key for item in page.items}
    assert "ex:Dog" in keys
    assert "ex:Animal" in keys


def test_mixed_kind_raises(ont):
    selections.upsert(ont, "ax_sel", SelectionKind.AXIOMS, ["a" * 64], "test")
    selections.upsert(ont, "ent_sel", SelectionKind.ENTITIES, ["ex:Dog"], "test")

    with pytest.raises(BadRequestError):
        selections.create(ont, "mixed_union", union=["ax_sel", "ent_sel"])


def test_empty_inputs_raises(ont):
    with pytest.raises(BadRequestError):
        selections.create(ont, "x", union=[])


def test_overwrite_produces_new_hash(ont):
    hash1 = selections.upsert(ont, "s", SelectionKind.ENTITIES, ["ex:Dog"], "test").content_hash
    _r = selections.upsert(ont, "s", SelectionKind.ENTITIES, ["ex:Cat"], "test")
    hash2, card2 = _r.content_hash, _r.cardinality

    assert hash2 != hash1
    assert card2 == 1
    assert selections.get(ont, "s").cardinality == 1


def test_write_if_hash_matches(ont):
    h1 = selections.upsert(ont, "s", SelectionKind.ENTITIES, ["ex:Dog"], "test").content_hash
    _r = selections.upsert(ont, "s", SelectionKind.ENTITIES, ["ex:Cat"], "test", if_hash=h1[:8])
    h2, card2 = _r.content_hash, _r.cardinality
    assert card2 == 1
    assert h2 != h1


def test_write_if_hash_mismatch_raises(ont):
    selections.upsert(ont, "s", SelectionKind.ENTITIES, ["ex:Dog"], "test")
    with pytest.raises(StaleSelectionError):
        selections.upsert(ont, "s", SelectionKind.ENTITIES, ["ex:Cat"], "test", if_hash="deadbeef")


def test_write_if_hash_missing_selection_raises(ont):
    with pytest.raises(StaleSelectionError):
        selections.upsert(
            ont, "ghost", SelectionKind.ENTITIES, ["ex:Cat"], "test", if_hash="abcd1234"
        )


def test_single_input_intersection_rejected(ont):
    selections.upsert(ont, "a", SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat"], "test")
    with pytest.raises(BadRequestError, match="at least two"):
        selections.create(ont, "r", intersection=["a"])


def test_single_input_difference_rejected(ont):
    selections.upsert(ont, "a", SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat"], "test")
    with pytest.raises(BadRequestError, match="at least two"):
        selections.create(ont, "r", difference=["a"])


def test_single_input_union_returns_copy(ont):
    selections.upsert(ont, "a", SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat"], "test")
    card = selections.create(ont, "r", union=["a"]).cardinality
    assert card == 2


# -- P-03-8: Selection validation and boundary cases --


def test_validate_selection_name_empty():
    with pytest.raises(BadRequestError):
        validate_selection_name("")


def test_validate_selection_name_with_at():
    with pytest.raises(BadRequestError):
        validate_selection_name("name@hash")


def test_validate_selection_name_too_long():
    with pytest.raises(BadRequestError):
        validate_selection_name("a" * 65)


@pytest.mark.parametrize("bad", ["foo\x00bar", "foo\nbar", "foo\tbar", "foo\x7fbar"])
def test_validate_selection_name_rejects_control_chars(bad):
    with pytest.raises(BadRequestError, match="control characters"):
        validate_selection_name(bad)


def test_validate_selection_name_valid():
    assert validate_selection_name("my_sel") == "my_sel"


def test_verify_hash_match_and_mismatch(ont):
    hash1 = selections.upsert(ont, "sel", SelectionKind.ENTITIES, ["ex:Dog"], "test").content_hash

    selections.verify_hash(ont, "sel", hash1[:8])  # should not raise

    with pytest.raises(StaleSelectionError):
        selections.verify_hash(ont, "sel", "00000000")


def test_read_with_show_filters(ont):
    ax = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    axioms.add(ont, [ax])
    real_hash = axiom_hash(ax)

    fake_hash = "d" * 64
    selections.upsert(ont, "sel", SelectionKind.AXIOMS, [real_hash, fake_hash], "test")

    page_present = selections.read(ont, "sel", show=ShowFilter.PRESENT)
    assert all(not item.missing for item in page_present.items)

    page_missing = selections.read(ont, "sel", show=ShowFilter.MISSING)
    assert all(item.missing for item in page_missing.items)

    page_all = selections.read(ont, "sel", show=ShowFilter.ALL)
    assert len(page_all.items) == 2


# -- P-03-8: LockedSelection validation --


def test_locked_selection_missing_at():
    with pytest.raises(ValueError):
        LockedSelection("no_at_sign_here")


def test_locked_selection_nonhex_prefix():
    with pytest.raises(ValueError):
        LockedSelection("sel@zzzzzzzz")


def test_locked_selection_full_64_char_accepted():
    LockedSelection("sel@" + "a" * 64)


# -- P-03-8: punned entity present+missing invariant --


def test_read_entities_selection_punned_entity_present_missing_sum(ont):
    # OWL punning: :X declared as both CLASS and NAMED_INDIVIDUAL (two Declaration axioms).
    # Entity selection containing :X must satisfy present + missing == cardinality.
    axioms.add(
        ont,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:X")),
            Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI("ex:X")),
        ],
    )
    # :ex:Ghost has no Declaration — should be counted as missing.
    selections.upsert(ont, "s", SelectionKind.ENTITIES, ["ex:X", "ex:Ghost"], "test")
    page = selections.read(ont, "s")
    assert page.present + page.missing == page.meta.cardinality
    assert page.present == 1  # ex:X is declared (punned, but COUNT(DISTINCT) = 1)
    assert page.missing == 1  # ex:Ghost has no Declaration


# -- P-03-9: selection hash round-trip --


def test_selection_hash_round_trip(ont):
    # Write items in arbitrary order. Read them back and re-write (in the order
    # they came back). The content hash must be stable across both writes because
    # _selection_hash sorts internally.
    items = ["ex:C", "ex:A", "ex:B"]
    result1 = selections.upsert(ont, "s", SelectionKind.ENTITIES, items, "test")
    page = selections.read(ont, "s")
    read_back = [item.key for item in page.items]
    result2 = selections.upsert(ont, "s2", SelectionKind.ENTITIES, read_back, "test")
    assert result1.content_hash == result2.content_hash
