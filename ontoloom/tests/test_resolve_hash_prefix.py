"""Hash-prefix resolution and AxiomHashPrefix validation."""

import pytest
from ontoloom.axioms.hashing import (
    AmbiguousHashError,
    AxiomHash,
    AxiomHashPrefix,
    AxiomNotFoundError,
    resolve_hash_prefix,
)


def test_axiom_hash_prefix_rejects_empty():
    """Empty prefix is rejected at the parse boundary."""
    with pytest.raises(ValueError, match="must not be empty"):
        AxiomHashPrefix("")


def test_axiom_hash_prefix_rejects_non_hex():
    with pytest.raises(ValueError, match="hex chars"):
        AxiomHashPrefix("not*hex")


def test_resolve_hash_prefix_not_found_raises(s):
    with pytest.raises(AxiomNotFoundError):
        resolve_hash_prefix(s, AxiomHashPrefix("deadbeef"))


_DECL_X = '{"annotations":[],"entity_type":"Class","iri":"ex:X"}'
_DECL_Y = '{"annotations":[],"entity_type":"Class","iri":"ex:Y"}'


def test_ambiguous_hash_error(s):
    prefix = "aaaa"
    h1 = prefix + "0" * 60
    h2 = prefix + "1" + "0" * 59
    s.conn.execute(
        "INSERT INTO axioms (hash, type, data) VALUES (?, 'Declaration', jsonb(?))",
        (h1, _DECL_X),
    )
    s.conn.execute(
        "INSERT INTO axioms (hash, type, data) VALUES (?, 'Declaration', jsonb(?))",
        (h2, _DECL_Y),
    )

    with pytest.raises(AmbiguousHashError) as exc_info:
        resolve_hash_prefix(s, AxiomHashPrefix(prefix))
    assert exc_info.value.count == 2
    assert exc_info.value.prefix == prefix
    assert len(exc_info.value.matches) == 2


def test_resolve_hash_prefix_range_scan(s):
    # Multiple hashes sharing a prefix get caught by the range scan; non-matching
    # hashes that sort just past the prefix boundary are excluded.
    near_miss = "9" + "0" * 63  # sorts immediately before any 'a*' hash
    sibling = "a" + "f" * 63
    target = "ab" + "0" * 62
    for h in (near_miss, sibling, target):
        s.conn.execute(
            "INSERT INTO axioms (hash, type, data) VALUES (?, 'Declaration', jsonb(?))",
            (h, _DECL_X),
        )

    assert resolve_hash_prefix(s, AxiomHashPrefix("ab")) == AxiomHash(target)

    with pytest.raises(AmbiguousHashError):
        resolve_hash_prefix(s, AxiomHashPrefix("a"))


def test_resolve_hash_prefix_upper_bound_edges(s):
    # The '9' -> ':' upper-bound increment must not include 'a*' hashes; the
    # 'f' -> 'g' increment must not pull in hashes outside the hex alphabet.
    hashes = [
        "9" + "0" * 63,
        "a" + "0" * 63,
        "f" + "0" * 63,
    ]
    for h in hashes:
        s.conn.execute(
            "INSERT INTO axioms (hash, type, data) VALUES (?, 'Declaration', jsonb(?))",
            (h, _DECL_X),
        )

    assert resolve_hash_prefix(s, AxiomHashPrefix("9")) == AxiomHash(hashes[0])
    assert resolve_hash_prefix(s, AxiomHashPrefix("f")) == AxiomHash(hashes[2])
