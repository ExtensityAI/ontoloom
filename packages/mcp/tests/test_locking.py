"""Tests for MCP-layer optimistic-locking refs and verify_lock."""

import pytest
from ontoloom.connection import Ontology, session
from ontoloom.prefixes.store import set_prefix
from ontoloom.prefixes.types import NamespaceIRI, PrefixName
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
    SelectionContentHash,
    SelectionKind,
    SelectionName,
    SelectionNotFoundError,
)
from ontoloom_mcp.components.locking import (
    HashPrefix,
    LockedAxiomSelectionName,
    LockedEntitySelectionName,
    StaleSelectionError,
    format_locked_quoted,
    verify_lock,
)


@pytest.fixture()
def s(tmp_path):
    path = tmp_path / "test.ontology.db"
    Ontology.create(path)
    with session(Ontology(path)) as sess:
        set_prefix(sess, PrefixName("ex"), NamespaceIRI("http://example.org/"))
        yield sess
        sess.commit()


# -- HashPrefix --


def test_hash_prefix_min_length():
    for short in ("a", "ab", "abcdefg"):
        with pytest.raises(ValueError, match="at least 8"):
            HashPrefix(short)

    HashPrefix("abcdef01")
    HashPrefix("a" * 16)


def test_hash_prefix_rejects_non_hex():
    with pytest.raises(ValueError):
        HashPrefix("xxxxxxxx")


# -- LockedEntitySelectionName --


def test_locked_entity_parse_fields():
    locked = LockedEntitySelectionName("entities:my_sel@a1b2c3d4")
    assert str(locked) == "entities:my_sel@a1b2c3d4"
    assert locked.bare == EntitySelectionName("entities:my_sel")
    assert locked.hash_prefix == "a1b2c3d4"
    assert locked.kind == SelectionKind.ENTITIES


def test_locked_entity_first_colon_split():
    locked = LockedEntitySelectionName("entities:ns:dogs@a1b2c3d4")
    assert locked.bare.bare == "ns:dogs"
    assert locked.hash_prefix == "a1b2c3d4"


def test_locked_entity_rejects_missing_at():
    with pytest.raises(ValueError):
        LockedEntitySelectionName("entities:my_sel")


def test_locked_entity_rejects_short_hash():
    with pytest.raises(ValueError):
        LockedEntitySelectionName("entities:my_sel@abc123")


def test_locked_entity_rejects_non_hex():
    with pytest.raises(ValueError):
        LockedEntitySelectionName("entities:my_sel@zzzzzzzz")


def test_locked_entity_rejects_axiom_prefix():
    with pytest.raises(ValueError):
        LockedEntitySelectionName("axioms:my_sel@a1b2c3d4")


# -- LockedAxiomSelectionName --


def test_locked_axiom_parse_fields():
    locked = LockedAxiomSelectionName("axioms:my_sel@deadbeef")
    assert str(locked) == "axioms:my_sel@deadbeef"
    assert locked.bare == AxiomSelectionName("axioms:my_sel")
    assert locked.hash_prefix == "deadbeef"
    assert locked.kind == SelectionKind.AXIOMS


def test_locked_axiom_rejects_entity_prefix():
    with pytest.raises(ValueError):
        LockedAxiomSelectionName("entities:my_sel@a1b2c3d4")


def test_locked_axiom_selection_name_lowercases_uppercase_hash_prefix():
    locked = LockedAxiomSelectionName("axioms:x@A3F1B2C4")
    assert locked.hash_prefix == "a3f1b2c4"


def test_locked_entity_selection_name_lowercases_uppercase_hash_prefix():
    locked = LockedEntitySelectionName("entities:x@A3F1B2C4")
    assert locked.hash_prefix == "a3f1b2c4"


# -- verify_lock --


def test_verify_lock_returns_bare_on_match(s):
    result = upsert_selection(s, SelectionName("cats"), SelectionKind.ENTITIES, ["ex:Cat"], "test")
    locked = LockedEntitySelectionName(f"entities:cats@{result.selection.hash[:8]}")

    bare = verify_lock(s, locked)
    assert isinstance(bare, EntitySelectionName)
    assert bare.bare == "cats"


def test_verify_lock_raises_not_found_on_missing(s):
    locked = LockedEntitySelectionName("entities:missing@deadbeef")

    with pytest.raises(SelectionNotFoundError):
        verify_lock(s, locked)


def test_verify_lock_raises_stale_on_hash_mismatch(s):
    upsert_selection(s, SelectionName("cats"), SelectionKind.ENTITIES, ["ex:Cat"], "test")
    locked = LockedEntitySelectionName("entities:cats@00000000")

    with pytest.raises(StaleSelectionError):
        verify_lock(s, locked)


def test_verify_lock_kind_mismatch_treated_as_missing(s):
    # A selection named "dogs" exists as ENTITIES; an AXIOMS lock with the same
    # name must not match -- separate (name, kind) row, so it's not found.
    upsert_selection(s, SelectionName("dogs"), SelectionKind.ENTITIES, ["ex:Dog"], "test")
    locked = LockedAxiomSelectionName("axioms:dogs@deadbeef")

    with pytest.raises(SelectionNotFoundError):
        verify_lock(s, locked)


# -- format_locked_quoted --


def test_format_locked_quoted_wraps_in_double_quotes(s):
    result = upsert_selection(s, SelectionName("ax_sel"), SelectionKind.AXIOMS, ["a" * 64], "test")
    assert format_locked_quoted(result.selection) == f'"axioms:ax_sel@{result.selection.hash}"'


# -- StaleSelectionError message format --


def test_stale_selection_error_shows_full_hash():
    full_hash = SelectionContentHash("0123456789abcdef")
    err = StaleSelectionError(
        SelectionName("cats"),
        HashPrefix("deadbeef"),
        full_hash,
        current_size=3,
    )
    assert full_hash in str(err)


def test_stale_selection_error_absent_hash_uses_placeholder():
    err = StaleSelectionError(
        SelectionName("cats"),
        HashPrefix("deadbeef"),
        None,
    )
    assert "<absent>" in str(err)
