"""Tests for `make_tag_resolver` — the structural dispatcher used by every
discriminated union in the codebase."""

from typing import Annotated, Any

import pytest
from ontoloom.models import FrozenModel, make_tag_resolver, tagged_union_meta
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
    resolve = make_tag_resolver((A, B))
    assert resolve({"x": 1, "y": 2}) == "A"
    assert resolve({"x": 1, "z": 2}) == "B"


def test_rejects_extra_keys():
    resolve = make_tag_resolver((A, B))
    # Input has keys not declared by either class.
    with pytest.raises(ValueError, match="could not dispatch"):
        resolve({"x": 1, "y": 2, "z": 3})


def test_rejects_missing_required_keys():
    resolve = make_tag_resolver((A, B))
    with pytest.raises(ValueError, match="could not dispatch"):
        resolve({"x": 1})


def test_picks_smallest_full_field_set_when_overlap():
    """When multiple classes match, the one with fewer total fields wins."""
    # JustExtra has {extra} (1 field). WithDefault has {x, extra} (2 fields,
    # only x required, so its full set is also a superset of {extra}).
    # JustExtra is the tighter fit.
    resolve = make_tag_resolver((WithDefault, JustExtra))
    assert resolve({"extra": 1}) == "JustExtra"


def test_stable_tiebreak_uses_input_order():
    class P(FrozenModel):
        v: int

    class Q(FrozenModel):
        v: int

    assert make_tag_resolver((P, Q))({"v": 1}) == "P"
    assert make_tag_resolver((Q, P))({"v": 1}) == "Q"


def test_dispatches_model_instance_via_class_name():
    resolve = make_tag_resolver((A, B))
    assert resolve(A(x=1, y=2)) == "A"


def test_excludes_annotations_key_by_default():
    resolve = make_tag_resolver((WithAnnotations,))
    assert resolve({"x": 1, "annotations": ()}) == "WithAnnotations"


def test_error_message_self_describes_dispatch_context():
    """The error must say it's a union-dispatch failure and list both the
    input keys and each candidate's required fields — without that context,
    a raw ValueError is impossible to debug."""
    resolve = make_tag_resolver((A, B))
    with pytest.raises(ValueError) as exc:
        resolve({"unrelated": 1})
    msg = str(exc.value)
    assert "could not dispatch input to any union member" in msg
    assert "union members: ['A', 'B']" in msg
    assert "input keys: ['unrelated']" in msg
    assert "A: required=['x', 'y']" in msg
    assert "B: required=['x', 'z']" in msg


# -- end-to-end: helper plugged into a Pydantic union -----------------------


def test_resolver_drives_pydantic_tagged_union():
    Either = Annotated[
        Annotated[A, Tag("A")] | Annotated[B, Tag("B")],
        *tagged_union_meta(make_tag_resolver((A, B))),
    ]
    adapter = TypeAdapter(Either)
    assert isinstance(adapter.validate_python({"x": 1, "y": 2}), A)
    assert isinstance(adapter.validate_python({"x": 1, "z": 3}), B)


def test_resolver_no_match_propagates_through_pydantic():
    """The resolver's ValueError reaches the caller intact (Pydantic propagates
    discriminator-callable raises rather than wrapping them)."""
    Either = Annotated[
        Annotated[A, Tag("A")] | Annotated[B, Tag("B")],
        *tagged_union_meta(make_tag_resolver((A, B))),
    ]
    adapter = TypeAdapter(Either)
    with pytest.raises(ValueError) as exc:
        adapter.validate_python({"unrelated": 1})
    assert "could not dispatch" in str(exc.value)
