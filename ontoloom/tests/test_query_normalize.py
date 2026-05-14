import random

import pytest
from ontoloom.hashing import AxiomHash
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType, Position
from ontoloom.prefixes.types import PrefixName
from ontoloom.query._constraints import (
    AlwaysFalse,
    Declared,
    HasEntityRole,
    InNamespaces,
    InPositions,
    InSelection,
    MentionedInAxioms,
    MentionsAll,
    MentionsAny,
    NotDeprecated,
    OfTypes,
    WithAnyProperty,
    WithIRIs,
    WithRoles,
)
from ontoloom.query._normalize import normalize_axiom, normalize_entity
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.selections.types import SelectionKind

# -- Test fixtures --

A = IRI(":A")
B = IRI(":B")
C = IRI(":C")
D = IRI(":D")

HASH_A = AxiomHash("a" * 64)
HASH_B = AxiomHash("b" * 64)

_AXIOM_REF = ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name="sel")
_ENTITY_REF = ResolvedSelection(kind=SelectionKind.ENTITIES, bare_name="sel")


# == Entity: empty input ==


def test_normalize_entity_empty():
    assert normalize_entity(()) == ()


# == Entity: intersection variants ==


def test_with_iris_intersection():
    result = normalize_entity([WithIRIs(iris=(A, B, C)), WithIRIs(iris=(B, C, D))])
    assert result == (WithIRIs(iris=(B, C)),)


def test_with_iris_empty_intersection_gives_always_false():
    result = normalize_entity([WithIRIs(iris=(A,)), WithIRIs(iris=(B,))])
    assert result == (AlwaysFalse(),)


def test_with_roles_intersection():
    result = normalize_entity(
        [
            WithRoles(roles=(EntityType.CLASS, EntityType.OBJECT_PROPERTY)),
            WithRoles(roles=(EntityType.CLASS, EntityType.DATA_PROPERTY)),
        ]
    )
    assert result == (WithRoles(roles=(EntityType.CLASS,)),)


def test_with_roles_empty_intersection_gives_always_false():
    result = normalize_entity(
        [
            WithRoles(roles=(EntityType.CLASS,)),
            WithRoles(roles=(EntityType.OBJECT_PROPERTY,)),
        ]
    )
    assert result == (AlwaysFalse(),)


def test_in_namespaces_intersection():
    ns_a = PrefixName("owl")
    ns_b = PrefixName("rdfs")
    ns_c = PrefixName("rdf")
    result = normalize_entity(
        [
            InNamespaces(namespaces=(ns_a, ns_b)),
            InNamespaces(namespaces=(ns_b, ns_c)),
        ]
    )
    assert result == (InNamespaces(namespaces=(ns_b,)),)


def test_in_namespaces_empty_intersection_gives_always_false():
    result = normalize_entity(
        [
            InNamespaces(namespaces=(PrefixName("owl"),)),
            InNamespaces(namespaces=(PrefixName("rdfs"),)),
        ]
    )
    assert result == (AlwaysFalse(),)


def test_in_positions_intersection():
    result = normalize_entity(
        [
            InPositions(positions=(Position.DOMAIN, Position.RANGE)),
            InPositions(positions=(Position.RANGE, Position.SUBJECT)),
        ]
    )
    assert result == (InPositions(positions=(Position.RANGE,)),)


def test_in_positions_empty_intersection_gives_always_false():
    result = normalize_entity(
        [
            InPositions(positions=(Position.DOMAIN,)),
            InPositions(positions=(Position.RANGE,)),
        ]
    )
    assert result == (AlwaysFalse(),)


# == Entity: single instances pass through unchanged ==


def test_with_iris_single_passthrough():
    c = WithIRIs(iris=(A, B))
    result = normalize_entity([c])
    assert result == (c,)


# == Entity: non-mergeable dedupe ==


def test_with_any_property_dedupe_equals():
    c = WithAnyProperty(properties=(A, B))
    result = normalize_entity([c, c])
    assert result == (c,)


def test_with_any_property_stay_separate():
    c1 = WithAnyProperty(properties=(A, B))
    c2 = WithAnyProperty(properties=(A,))
    result = normalize_entity([c1, c2])
    assert len(result) == 2
    assert set(result) == {c1, c2}


def test_mentioned_in_axioms_dedupe_equals():
    c = MentionedInAxioms(hashes=(HASH_A, HASH_B))
    result = normalize_entity([c, c])
    assert result == (c,)


def test_mentioned_in_axioms_stay_separate():
    c1 = MentionedInAxioms(hashes=(HASH_A,))
    c2 = MentionedInAxioms(hashes=(HASH_B,))
    result = normalize_entity([c1, c2])
    assert len(result) == 2
    assert set(result) == {c1, c2}


# == Entity: Declared ==


def test_declared_same_state_dedupe():
    result = normalize_entity([Declared(state=True), Declared(state=True)])
    assert result == (Declared(state=True),)


def test_declared_conflict_gives_always_false():
    result = normalize_entity([Declared(state=True), Declared(state=False)])
    assert result == (AlwaysFalse(),)


# == Entity: nullary dedupe ==


def test_has_entity_role_dedupe():
    result = normalize_entity([HasEntityRole(), HasEntityRole()])
    assert result == (HasEntityRole(),)


def test_not_deprecated_dedupe():
    result = normalize_entity([NotDeprecated(), NotDeprecated()])
    assert result == (NotDeprecated(),)


# == Entity: InSelection ==


def test_in_selection_single_passes_through():
    c = InSelection(ref=_ENTITY_REF)
    result = normalize_entity([c, WithIRIs(iris=(A,))])
    assert InSelection(ref=_ENTITY_REF) in result


def test_in_selection_multiple_raises():
    c = InSelection(ref=_ENTITY_REF)

    with pytest.raises(ValueError, match="a query may have at most one selection scope"):
        normalize_entity([c, c])


# == Entity: AlwaysFalse short-circuit ==


def test_always_false_swallows_everything():
    result = normalize_entity(
        [WithIRIs(iris=(A,)), AlwaysFalse(), HasEntityRole(), Declared(state=True)]
    )
    assert result == (AlwaysFalse(),)


def test_always_false_at_start():
    result = normalize_entity([AlwaysFalse(), WithIRIs(iris=(A,))])
    assert result == (AlwaysFalse(),)


def test_always_false_at_end():
    result = normalize_entity([WithIRIs(iris=(A,)), AlwaysFalse()])
    assert result == (AlwaysFalse(),)


# == Entity: idempotency ==


def test_normalize_entity_idempotent():
    cs: list = [
        WithIRIs(iris=(A, B, C)),
        WithIRIs(iris=(B, C, D)),
        WithRoles(roles=(EntityType.CLASS, EntityType.OBJECT_PROPERTY)),
        HasEntityRole(),
        HasEntityRole(),
        NotDeprecated(),
        Declared(state=True),
        Declared(state=True),
        WithAnyProperty(properties=(A,)),
        MentionedInAxioms(hashes=(HASH_A,)),
    ]
    first = normalize_entity(cs)
    second = normalize_entity(first)
    assert first == second


# == Entity: order-insensitivity ==


def test_normalize_entity_order_insensitive():
    cs: list = [
        WithIRIs(iris=(A, B, C)),
        WithIRIs(iris=(B, C, D)),
        HasEntityRole(),
        NotDeprecated(),
        Declared(state=True),
        WithAnyProperty(properties=(A,)),
    ]
    shuffled = list(cs)
    random.shuffle(shuffled)
    assert normalize_entity(cs) == normalize_entity(shuffled)


# ============================================================
# Axiom tests
# ============================================================


def test_normalize_axiom_empty():
    assert normalize_axiom(()) == ()


# == Axiom: OfTypes intersection ==


def test_of_types_intersection():
    result = normalize_axiom(
        [
            OfTypes(tags=("SubClassOf", "EquivalentClasses")),
            OfTypes(tags=("SubClassOf", "ObjectPropertyRange")),
        ]
    )
    assert result == (OfTypes(tags=("SubClassOf",)),)


def test_of_types_empty_intersection_gives_always_false():
    result = normalize_axiom([OfTypes(tags=("SubClassOf",)), OfTypes(tags=("EquivalentClasses",))])
    assert result == (AlwaysFalse(),)


def test_of_types_single_passthrough():
    c = OfTypes(tags=("SubClassOf",))
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


# == Axiom: MentionsAny non-mergeable ==


def test_mentions_any_dedupe_equals():
    c = MentionsAny(iris=(A, B))
    result = normalize_axiom([c, c])
    assert result == (c,)


def test_mentions_any_stay_separate():
    c1 = MentionsAny(iris=(A, B))
    c2 = MentionsAny(iris=(A,))
    result = normalize_axiom([c1, c2])
    assert len(result) == 2
    assert set(result) == {c1, c2}


# == Axiom: InSelection ==


def test_axiom_in_selection_single_passes_through():
    c = InSelection(ref=_AXIOM_REF)
    result = normalize_axiom([c, OfTypes(tags=("SubClassOf",))])
    assert InSelection(ref=_AXIOM_REF) in result


def test_axiom_in_selection_multiple_raises():
    c = InSelection(ref=_AXIOM_REF)

    with pytest.raises(ValueError, match="a query may have at most one selection scope"):
        normalize_axiom([c, c])


# == Axiom: AlwaysFalse short-circuit ==


def test_axiom_always_false_swallows_everything():
    result = normalize_axiom([OfTypes(tags=("SubClassOf",)), AlwaysFalse(), MentionsAll(iris=(A,))])
    assert result == (AlwaysFalse(),)


# == Axiom: idempotency ==


def test_normalize_axiom_idempotent():
    cs: list = [
        OfTypes(tags=("SubClassOf", "EquivalentClasses")),
        OfTypes(tags=("SubClassOf", "ObjectPropertyRange")),
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
        OfTypes(tags=("SubClassOf", "EquivalentClasses")),
        OfTypes(tags=("SubClassOf", "ObjectPropertyRange")),
        MentionsAll(iris=(A, B)),
        MentionsAny(iris=(A,)),
        MentionsAny(iris=(B,)),
    ]
    shuffled = list(cs)
    random.shuffle(shuffled)
    assert normalize_axiom(cs) == normalize_axiom(shuffled)
