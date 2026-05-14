import pytest
from ontoloom.query._selection_ref import (
    LockedSelectionRef,
    ResolvedSelection,
    SelectionRef,
    resolve_selection,
)
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import (
    SelectionKind,
    SelectionNotFoundError,
    StaleSelectionError,
)

# -- SelectionRef.parse --


def test_selection_ref_parse_roundtrip():
    ref = SelectionRef.parse("axioms:my_sel")
    assert str(ref) == "axioms:my_sel"


def test_selection_ref_parse_entities_roundtrip():
    ref = SelectionRef.parse("entities:my_sel")
    assert str(ref) == "entities:my_sel"


def test_selection_ref_parse_first_colon_split():
    ref = SelectionRef.parse("axioms:ns:dogs")
    assert ref.kind == SelectionKind.AXIOMS
    assert ref.bare_name == "ns:dogs"


def test_selection_ref_parse_fields():
    ref = SelectionRef.parse("entities:my_sel")
    assert ref.kind == SelectionKind.ENTITIES
    assert ref.bare_name == "my_sel"


def test_selection_ref_parse_missing_colon():
    with pytest.raises(ValueError, match="kind:bare_name"):
        SelectionRef.parse("axioms_my_sel")


def test_selection_ref_parse_unknown_kind():
    with pytest.raises(ValueError, match="Unknown selection kind"):
        SelectionRef.parse("blobs:my_sel")


def test_selection_ref_parse_empty_bare_name():
    with pytest.raises(ValueError):
        SelectionRef.parse("axioms:")


def test_selection_ref_parse_invalid_bare_name_chars():
    with pytest.raises(ValueError):
        SelectionRef.parse("axioms:bad name")


def test_selection_ref_parse_bare_name_starts_with_digit():
    with pytest.raises(ValueError):
        SelectionRef.parse("axioms:1invalid")


# -- LockedSelectionRef.parse --


def test_locked_selection_ref_parse_roundtrip():
    ref = LockedSelectionRef.parse("axioms:my_sel@a1b2c3d4")
    assert str(ref) == "axioms:my_sel@a1b2c3d4"


def test_locked_selection_ref_parse_first_colon_last_at():
    ref = LockedSelectionRef.parse("axioms:ns:dogs@a1b2c3d4")
    assert ref.kind == SelectionKind.AXIOMS
    assert ref.bare_name == "ns:dogs"
    assert ref.hash_prefix == "a1b2c3d4"


def test_locked_selection_ref_parse_fields():
    ref = LockedSelectionRef.parse("entities:my_sel@deadbeef")
    assert ref.kind == SelectionKind.ENTITIES
    assert ref.bare_name == "my_sel"
    assert ref.hash_prefix == "deadbeef"


def test_locked_selection_ref_parse_missing_at():
    with pytest.raises(ValueError):
        LockedSelectionRef.parse("axioms:my_sel")


def test_locked_selection_ref_parse_hash_too_short():
    with pytest.raises(ValueError, match="hex"):
        LockedSelectionRef.parse("axioms:my_sel@abc123")  # only 6 hex chars


def test_locked_selection_ref_parse_hash_non_hex():
    with pytest.raises(ValueError, match="hex"):
        LockedSelectionRef.parse("axioms:my_sel@zzzzzzzz")


def test_locked_selection_ref_parse_unknown_kind():
    with pytest.raises(ValueError, match="Unknown selection kind"):
        LockedSelectionRef.parse("blobs:my_sel@a1b2c3d4")


def test_locked_selection_ref_parse_bare_name_cannot_contain_at():
    # '@' in bare_name is ambiguous — rsplit('@',1) would eat the last '@' as hash separator
    # Verify this is rejected via the hash-prefix pattern check (bare_name becomes non-empty
    # but hash_prefix would be invalid hex)
    with pytest.raises(ValueError):
        LockedSelectionRef.parse("axioms:bad@name@a1b2c3d4")


# -- resolve_selection with SelectionRef --


def test_resolve_selection_ref_success(s):
    upsert_selection(s, "dogs", SelectionKind.ENTITIES, ["ex:Dog", "ex:Poodle"], "test")

    ref = SelectionRef(kind=SelectionKind.ENTITIES, bare_name="dogs")
    resolved = resolve_selection(s, ref)

    assert isinstance(resolved, ResolvedSelection)
    assert resolved.kind == SelectionKind.ENTITIES
    assert resolved.bare_name == "dogs"


def test_resolve_selection_ref_not_found_wrong_name(s):
    ref = SelectionRef(kind=SelectionKind.ENTITIES, bare_name="nonexistent")

    with pytest.raises(SelectionNotFoundError):
        resolve_selection(s, ref)


def test_resolve_selection_ref_not_found_wrong_kind(s):
    upsert_selection(s, "dogs", SelectionKind.ENTITIES, ["ex:Dog"], "test")

    # Same name, wrong kind — must raise SelectionNotFoundError (two-column query)
    ref = SelectionRef(kind=SelectionKind.AXIOMS, bare_name="dogs")

    with pytest.raises(SelectionNotFoundError):
        resolve_selection(s, ref)


# -- resolve_selection with LockedSelectionRef --


def test_resolve_locked_selection_ref_success(s):
    result = upsert_selection(s, "cats", SelectionKind.ENTITIES, ["ex:Cat"], "test")
    hash_prefix = result.selection.hash[:8]

    ref = LockedSelectionRef(
        kind=SelectionKind.ENTITIES,
        bare_name="cats",
        hash_prefix=hash_prefix,
    )
    resolved = resolve_selection(s, ref)

    assert isinstance(resolved, ResolvedSelection)
    assert resolved.kind == SelectionKind.ENTITIES
    assert resolved.bare_name == "cats"


def test_resolve_locked_selection_ref_stale(s):
    upsert_selection(s, "cats", SelectionKind.ENTITIES, ["ex:Cat"], "test")

    ref = LockedSelectionRef(
        kind=SelectionKind.ENTITIES,
        bare_name="cats",
        hash_prefix="00000000",  # wrong hash prefix
    )

    with pytest.raises(StaleSelectionError):
        resolve_selection(s, ref)


def test_resolved_selection_str():
    r = ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name="my_sel")
    assert str(r) == "axioms:my_sel"
