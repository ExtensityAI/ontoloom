"""Tests for `make_tag_resolver` — the structural dispatcher used by every
discriminated union in the codebase."""

from typing import Annotated

import pytest
from ontoloom.models import (
    FrozenModel,
    UnionDispatchError,
    make_tag_resolver,
    tagged_union_meta,
)
from pydantic import Tag, TypeAdapter

# -- fixtures ---------------------------------------------------------------


class A(FrozenModel):
    x: int
    y: int


class B(FrozenModel):
    x: int
    z: int


class WithDefault(FrozenModel):
    x: int
    extra: int = 0


class JustExtra(FrozenModel):
    extra: int


class WithAnnotations(FrozenModel):
    annotations: tuple[str, ...] = ()
    x: int


# -- core dispatch behavior -------------------------------------------------


def test_routes_unique_signatures():
    resolve = make_tag_resolver((A, B), union_name="AB")
    assert resolve({"x": 1, "y": 2}) == "A"
    assert resolve({"x": 1, "z": 2}) == "B"


def test_rejects_extra_keys():
    resolve = make_tag_resolver((A, B), union_name="AB")
    with pytest.raises(UnionDispatchError) as exc:
        resolve({"x": 1, "y": 2, "z": 3})
    e = exc.value
    assert e.union_name == "AB"
    assert e.unknown == frozenset({"z"})


def test_rejects_missing_required_keys():
    resolve = make_tag_resolver((A, B), union_name="AB")
    with pytest.raises(UnionDispatchError) as exc:
        resolve({"x": 1})
    e = exc.value
    # Both A and B share required {x, y} or {x, z}; with just {x}, both score
    # |req ∩ keys| = 1, |keys - full| = 0, |req - keys| = 1. Tiebreaker picks
    # first listed -> A.
    assert e.closest_variant == "A"
    assert e.missing == frozenset({"y"})
    assert e.unknown == frozenset()


def test_picks_smallest_full_field_set_when_overlap():
    """When multiple classes match, the one with fewer total fields wins."""
    resolve = make_tag_resolver((WithDefault, JustExtra), union_name="WD")
    assert resolve({"extra": 1}) == "JustExtra"


def test_stable_tiebreak_uses_input_order():
    class P(FrozenModel):
        v: int

    class Q(FrozenModel):
        v: int

    assert make_tag_resolver((P, Q), union_name="PQ")({"v": 1}) == "P"
    assert make_tag_resolver((Q, P), union_name="QP")({"v": 1}) == "Q"


def test_dispatches_model_instance_via_class_name():
    resolve = make_tag_resolver((A, B), union_name="AB")
    assert resolve(A(x=1, y=2)) == "A"


def test_excludes_annotations_key_by_default():
    resolve = make_tag_resolver((WithAnnotations,), union_name="WA")
    assert resolve({"x": 1, "annotations": ()}) == "WithAnnotations"


# -- error structure --------------------------------------------------------


def test_dispatch_error_carries_union_name():
    resolve = make_tag_resolver((A, B), union_name="MyUnion")
    with pytest.raises(UnionDispatchError) as exc:
        resolve({"unrelated": 1})
    assert exc.value.union_name == "MyUnion"


def test_dispatch_error_picks_best_fit_by_required_overlap():
    """Best-fit ranks variants by |req ∩ keys|: more required fields satisfied wins."""

    class Two(FrozenModel):
        a: int
        b: int

    class Three(FrozenModel):
        a: int
        c: int
        d: int

    resolve = make_tag_resolver((Two, Three), union_name="U")
    # Input has {a, c}: Three has 2 of 3 required satisfied; Two has 1 of 2.
    # |req ∩ keys|: Three=2, Two=1 -> Three wins.
    with pytest.raises(UnionDispatchError) as exc:
        resolve({"a": 1, "c": 2})
    assert exc.value.closest_variant == "Three"
    assert exc.value.missing == frozenset({"d"})
    assert exc.value.unknown == frozenset()


def test_dispatch_error_message_is_single_line_and_focused():
    """The default str(error) emits a focused single-line message — no wall."""
    resolve = make_tag_resolver((A, B), union_name="AB")
    with pytest.raises(UnionDispatchError) as exc:
        resolve({"x": 1, "extra": 99})
    msg = str(exc.value)
    assert "AB" in msg
    assert "missing" in msg or "unknown" in msg
    # No multi-line signature dump:
    assert "\n" not in msg


def test_dispatch_error_empty_input_picks_smallest_required():
    """Empty input has no signal; tiebreaker (-|req - keys|) prefers the variant
    with the smallest required set."""

    class Big(FrozenModel):
        a: int
        b: int
        c: int

    class Small(FrozenModel):
        a: int

    resolve = make_tag_resolver((Big, Small), union_name="U")
    with pytest.raises(UnionDispatchError) as exc:
        resolve({})
    assert exc.value.closest_variant == "Small"
    assert exc.value.missing == frozenset({"a"})


# -- end-to-end: helper plugged into a Pydantic union -----------------------


def test_resolver_drives_pydantic_tagged_union():
    either = Annotated[
        Annotated[A, Tag("A")] | Annotated[B, Tag("B")],
        *tagged_union_meta(make_tag_resolver((A, B), union_name="Either")),
    ]
    adapter = TypeAdapter(either)
    assert isinstance(adapter.validate_python({"x": 1, "y": 2}), A)
    assert isinstance(adapter.validate_python({"x": 1, "z": 3}), B)


def test_resolver_no_match_propagates_through_pydantic_untouched():
    """UnionDispatchError reaches the caller as itself — Pydantic only wraps
    ValueError/AssertionError, not arbitrary exceptions."""
    either = Annotated[
        Annotated[A, Tag("A")] | Annotated[B, Tag("B")],
        *tagged_union_meta(make_tag_resolver((A, B), union_name="Either")),
    ]
    adapter = TypeAdapter(either)
    with pytest.raises(UnionDispatchError) as exc:
        adapter.validate_python({"unrelated": 1})
    assert exc.value.union_name == "Either"
