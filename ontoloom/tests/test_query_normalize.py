import random
from collections.abc import Sequence
from typing import Any

import pytest
from ontoloom.axioms.hashing import AxiomHash
from ontoloom.owl.axioms import AxiomTag
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType, Position
from ontoloom.prefixes.types import PrefixName
from ontoloom.query._normalize import normalize_axiom, normalize_entity
from ontoloom.query.constraints import (
    AlwaysFalse,
    Declared,
    Deprecated,
    HasAnyAnnotation,
    HasAnyProperty,
    HasRole,
    InAxiomSelection,
    InEntitySelection,
    InIRIs,
    InNamespaces,
    InPositions,
    MentionedIn,
    MentionsAll,
    MentionsAllOverflowError,
    MentionsAny,
    WithRoles,
    WithTypes,
)
from ontoloom.selections.types import SelectionName

# -- Test fixtures --

A = IRI(":A")
B = IRI(":B")
C = IRI(":C")
D = IRI(":D")

HASH_A = AxiomHash("a" * 64)
HASH_B = AxiomHash("b" * 64)

_AXIOM_REF = SelectionName("sel")
_ENTITY_REF = SelectionName("sel")


# == Entity: empty input ==


def test_normalize_entity_empty():
    assert normalize_entity(()) == ()


# == Entity: intersection variants ==

_NS_A = PrefixName("owl")
_NS_B = PrefixName("rdfs")
_NS_C = PrefixName("rdf")


@pytest.mark.parametrize(
    ("a", "b", "merged"),
    [
        pytest.param(
            InIRIs(iris=(A, B, C)),
            InIRIs(iris=(B, C, D)),
            InIRIs(iris=(B, C)),
            id="in_iris",
        ),
        pytest.param(
            WithRoles(roles=(EntityType.CLASS, EntityType.OBJECT_PROPERTY)),
            WithRoles(roles=(EntityType.CLASS, EntityType.DATA_PROPERTY)),
            WithRoles(roles=(EntityType.CLASS,)),
            id="with_roles",
        ),
        pytest.param(
            InNamespaces(namespaces=(_NS_A, _NS_B)),
            InNamespaces(namespaces=(_NS_B, _NS_C)),
            InNamespaces(namespaces=(_NS_B,)),
            id="in_namespaces",
        ),
        pytest.param(
            InPositions(positions=(Position.DOMAIN, Position.RANGE)),
            InPositions(positions=(Position.RANGE, Position.SUBJECT)),
            InPositions(positions=(Position.RANGE,)),
            id="in_positions",
        ),
    ],
)
def test_entity_intersection(a: Any, b: Any, merged: Any):
    assert normalize_entity([a, b]) == (merged,)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        pytest.param(InIRIs(iris=(A,)), InIRIs(iris=(B,)), id="in_iris"),
        pytest.param(
            WithRoles(roles=(EntityType.CLASS,)),
            WithRoles(roles=(EntityType.OBJECT_PROPERTY,)),
            id="with_roles",
        ),
        pytest.param(
            InNamespaces(namespaces=(PrefixName("owl"),)),
            InNamespaces(namespaces=(PrefixName("rdfs"),)),
            id="in_namespaces",
        ),
        pytest.param(
            InPositions(positions=(Position.DOMAIN,)),
            InPositions(positions=(Position.RANGE,)),
            id="in_positions",
        ),
    ],
)
def test_entity_empty_intersection_gives_always_false(a: Any, b: Any):
    assert normalize_entity([a, b]) == (AlwaysFalse(),)


# == Entity: single instances pass through unchanged ==


def test_with_iris_single_passthrough():
    c = InIRIs(iris=(A, B))
    result = normalize_entity([c])
    assert result == (c,)


# == Entity: non-mergeable dedupe ==


@pytest.mark.parametrize(
    ("equal", "distinct"),
    [
        pytest.param(
            HasAnyProperty(properties=(A, B)),
            HasAnyProperty(properties=(A,)),
            id="has_any_property",
        ),
        pytest.param(
            MentionedIn(hashes=(HASH_A, HASH_B)),
            MentionedIn(hashes=(HASH_A,)),
            id="mentioned_in",
        ),
    ],
)
def test_entity_non_mergeable_dedupe(equal: Any, distinct: Any):
    assert normalize_entity([equal, equal]) == (equal,)
    result = normalize_entity([equal, distinct])
    assert len(result) == 2
    assert set(result) == {equal, distinct}


# == Entity: Declared ==


def test_declared_same_state_dedupe():
    result = normalize_entity([Declared(state=True), Declared(state=True)])
    assert result == (Declared(state=True),)


def test_declared_conflict_gives_always_false():
    result = normalize_entity([Declared(state=True), Declared(state=False)])
    assert result == (AlwaysFalse(),)


# == Entity: nullary dedupe ==


def test_has_entity_role_dedupe():
    result = normalize_entity([HasRole(), HasRole()])
    assert result == (HasRole(),)


def test_not_deprecated_dedupe():
    result = normalize_entity([Deprecated(state=False), Deprecated(state=False)])
    assert result == (Deprecated(state=False),)


# == Entity: InAxiomSelection / InEntitySelection ==


def test_in_selection_single_passes_through():
    c = InEntitySelection(name=_ENTITY_REF)
    result = normalize_entity([c, InIRIs(iris=(A,))])
    assert InEntitySelection(name=_ENTITY_REF) in result


def test_in_selection_multiple_raises():
    c = InEntitySelection(name=_ENTITY_REF)

    with pytest.raises(ValueError, match="a query may have at most one selection scope"):
        normalize_entity([c, c])


# == Entity: AlwaysFalse short-circuit ==


@pytest.mark.parametrize(
    "cs",
    [
        pytest.param(
            [InIRIs(iris=(A,)), AlwaysFalse(), HasRole(), Declared(state=True)],
            id="middle",
        ),
        pytest.param([AlwaysFalse(), InIRIs(iris=(A,))], id="start"),
        pytest.param([InIRIs(iris=(A,)), AlwaysFalse()], id="end"),
    ],
)
def test_always_false_swallows_everything(cs: Sequence[Any]):
    assert normalize_entity(cs) == (AlwaysFalse(),)


# == Entity: idempotency ==


def test_normalize_entity_idempotent():
    cs: list = [
        InIRIs(iris=(A, B, C)),
        InIRIs(iris=(B, C, D)),
        WithRoles(roles=(EntityType.CLASS, EntityType.OBJECT_PROPERTY)),
        HasRole(),
        HasRole(),
        Deprecated(state=False),
        Declared(state=True),
        Declared(state=True),
        HasAnyProperty(properties=(A,)),
        MentionedIn(hashes=(HASH_A,)),
    ]
    first = normalize_entity(cs)
    second = normalize_entity(first)
    assert first == second


# == Entity: order-insensitivity ==


def test_normalize_entity_order_insensitive():
    cs: list = [
        InIRIs(iris=(A, B, C)),
        InIRIs(iris=(B, C, D)),
        HasRole(),
        Deprecated(state=False),
        Declared(state=True),
        HasAnyProperty(properties=(A,)),
    ]
    shuffled = list(cs)
    random.shuffle(shuffled)
    assert normalize_entity(cs) == normalize_entity(shuffled)


# ============================================================
# Axiom tests
# ============================================================


def test_normalize_axiom_empty():
    assert normalize_axiom(()) == ()


# == Axiom: WithTypes intersection ==


def test_of_types_intersection():
    result = normalize_axiom(
        [
            WithTypes(tags=(AxiomTag.SUB_CLASS_OF, AxiomTag.EQUIVALENT_CLASSES)),
            WithTypes(tags=(AxiomTag.SUB_CLASS_OF, AxiomTag.OBJECT_PROPERTY_RANGE)),
        ]
    )
    assert result == (WithTypes(tags=(AxiomTag.SUB_CLASS_OF,)),)


def test_of_types_empty_intersection_gives_always_false():
    result = normalize_axiom(
        [WithTypes(tags=(AxiomTag.SUB_CLASS_OF,)), WithTypes(tags=(AxiomTag.EQUIVALENT_CLASSES,))]
    )
    assert result == (AlwaysFalse(),)


def test_of_types_single_passthrough():
    c = WithTypes(tags=(AxiomTag.SUB_CLASS_OF,))
    result = normalize_axiom([c])
    assert result == (c,)


# == Axiom: MentionsAll union ==


def test_mentions_all_union():
    result = normalize_axiom([MentionsAll(iris=(A, B)), MentionsAll(iris=(B, C))])
    assert result == (MentionsAll(iris=(A, B, C)),)


def test_mentions_all_single_passthrough():
    c = MentionsAll(iris=(A, B))
    result = normalize_axiom([c])
    assert result == (c,)


def test_mentions_all_dedupe_equals():
    c = MentionsAll(iris=(A, B))
    result = normalize_axiom([c, c])
    assert result == (c,)


def test_normalize_axiom_mentions_all_overflow_raises_clear_error():
    iris_a = tuple(IRI(f":A{i}") for i in range(5))
    iris_b = (IRI(":A4"), *(IRI(f":B{i}") for i in range(4)))

    with pytest.raises(MentionsAllOverflowError) as excinfo:
        normalize_axiom([MentionsAll(iris=iris_a), MentionsAll(iris=iris_b)])

    assert excinfo.value.count == 9
    assert excinfo.value.cap == 8
    msg = str(excinfo.value)
    assert "9" in msg
    assert "8" in msg


# == Axiom: non-mergeable dedupe ==


@pytest.mark.parametrize(
    ("equal", "distinct"),
    [
        pytest.param(
            MentionsAny(iris=(A, B)),
            MentionsAny(iris=(A,)),
            id="mentions_any",
        ),
    ],
)
def test_axiom_non_mergeable_dedupe(equal: Any, distinct: Any):
    assert normalize_axiom([equal, equal]) == (equal,)
    result = normalize_axiom([equal, distinct])
    assert len(result) == 2
    assert set(result) == {equal, distinct}


# == Axiom: annotation-constraint dedupe ==


def test_normalize_axiom_annotation_dedupe():
    c = HasAnyAnnotation(properties=(IRI("ex:p"),))
    assert normalize_axiom([c, c]) == (c,)


# == Axiom: InAxiomSelection / InEntitySelection ==


def test_axiom_in_selection_single_passes_through():
    c = InAxiomSelection(name=_AXIOM_REF)
    result = normalize_axiom([c, WithTypes(tags=(AxiomTag.SUB_CLASS_OF,))])
    assert InAxiomSelection(name=_AXIOM_REF) in result


def test_axiom_in_selection_multiple_raises():
    c = InAxiomSelection(name=_AXIOM_REF)

    with pytest.raises(ValueError, match="a query may have at most one selection scope"):
        normalize_axiom([c, c])


# == Axiom: AlwaysFalse short-circuit ==


def test_axiom_always_false_swallows_everything():
    result = normalize_axiom(
        [WithTypes(tags=(AxiomTag.SUB_CLASS_OF,)), AlwaysFalse(), MentionsAll(iris=(A,))]
    )
    assert result == (AlwaysFalse(),)


# == Axiom: idempotency ==


def test_normalize_axiom_idempotent():
    cs: list = [
        WithTypes(tags=(AxiomTag.SUB_CLASS_OF, AxiomTag.EQUIVALENT_CLASSES)),
        WithTypes(tags=(AxiomTag.SUB_CLASS_OF, AxiomTag.OBJECT_PROPERTY_RANGE)),
        MentionsAll(iris=(A, B)),
        MentionsAll(iris=(B, C)),
        MentionsAny(iris=(A,)),
        MentionsAny(iris=(A,)),
    ]
    first = normalize_axiom(cs)
    second = normalize_axiom(first)
    assert first == second


# == Axiom: order-insensitivity ==


def test_normalize_axiom_order_insensitive():
    cs: list = [
        WithTypes(tags=(AxiomTag.SUB_CLASS_OF, AxiomTag.EQUIVALENT_CLASSES)),
        WithTypes(tags=(AxiomTag.SUB_CLASS_OF, AxiomTag.OBJECT_PROPERTY_RANGE)),
        MentionsAll(iris=(A, B)),
        MentionsAny(iris=(A,)),
        MentionsAny(iris=(B,)),
    ]
    shuffled = list(cs)
    random.shuffle(shuffled)
    assert normalize_axiom(cs) == normalize_axiom(shuffled)


# == Exhaustiveness: unknown variant raises ==


class _UnknownConstraint:
    """A synthetic constraint variant the normalizer doesn't know about."""


def test_normalize_entity_raises_on_unknown_variant():
    with pytest.raises(ValueError, match="unknown entity constraint variant"):
        normalize_entity([_UnknownConstraint()])  # pyright: ignore[reportArgumentType]


def test_normalize_axiom_raises_on_unknown_variant():
    with pytest.raises(ValueError, match="unknown axiom constraint variant"):
        normalize_axiom([_UnknownConstraint()])  # pyright: ignore[reportArgumentType]
