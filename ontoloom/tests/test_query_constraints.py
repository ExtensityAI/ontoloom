import pytest
from ontoloom.hashing import AxiomHash
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import AxiomTag, EntityType, Position
from ontoloom.prefixes.types import PrefixName
from ontoloom.query.constraints import (
    AlwaysFalse,
    Declared,
    Deprecated,
    HasAnyProperty,
    HasRole,
    InIRIs,
    InNamespaces,
    InPositions,
    InSelection,
    MentionedIn,
    MentionsAll,
    MentionsAny,
    WithRoles,
    WithTypes,
)
from ontoloom.selections.types import AxiomSelectionName, EntitySelectionName
from pydantic import ValidationError

# -- Helpers --

A = IRI(":A")
B = IRI(":B")
C = IRI(":C")

HASH_A = AxiomHash("a" * 64)
HASH_B = AxiomHash("b" * 64)
HASH_C = AxiomHash("c" * 64)


# -- InIRIs --


def test_with_iris_empty_raises():
    with pytest.raises(ValidationError):
        InIRIs(iris=())


def test_with_iris_set_semantics_order_insensitive():
    assert InIRIs(iris=(B, A)) == InIRIs(iris=(A, B))


def test_with_iris_dedupe():
    result = InIRIs(iris=(A, A, B))
    assert len(result.iris) == 2
    assert set(result.iris) == {A, B}


def test_with_iris_sorted():
    result = InIRIs(iris=(B, A))
    assert result.iris == tuple(sorted({A, B}))


# -- WithRoles --


def test_with_roles_empty_raises():
    with pytest.raises(ValidationError):
        WithRoles(roles=())


def test_with_roles_set_semantics_order_insensitive():
    assert WithRoles(roles=(EntityType.CLASS, EntityType.NAMED_INDIVIDUAL)) == WithRoles(
        roles=(EntityType.NAMED_INDIVIDUAL, EntityType.CLASS)
    )


def test_with_roles_dedupe():
    result = WithRoles(roles=(EntityType.CLASS, EntityType.CLASS, EntityType.DATA_PROPERTY))
    assert len(result.roles) == 2
    assert set(result.roles) == {EntityType.CLASS, EntityType.DATA_PROPERTY}


# -- HasRole --


def test_has_entity_role_constructs():
    r = HasRole()
    assert isinstance(r, HasRole)


# -- InNamespaces --


def test_in_namespaces_empty_raises():
    with pytest.raises(ValidationError):
        InNamespaces(namespaces=())


def test_in_namespaces_set_semantics_order_insensitive():
    ns_a = PrefixName("owl")
    ns_b = PrefixName("rdfs")
    assert InNamespaces(namespaces=(ns_b, ns_a)) == InNamespaces(namespaces=(ns_a, ns_b))


def test_in_namespaces_dedupe():
    ns = PrefixName("owl")
    result = InNamespaces(namespaces=(ns, ns))
    assert len(result.namespaces) == 1


# -- Declared --


def test_declared_true():
    d = Declared(state=True)
    assert d.state is True


def test_declared_false():
    d = Declared(state=False)
    assert d.state is False


def test_declared_no_default_raises():
    with pytest.raises(ValidationError):
        Declared()  # pyright: ignore[reportCallIssue]


# -- Deprecated --


def test_deprecated_state_false_constructs():
    nd = Deprecated(state=False)
    assert isinstance(nd, Deprecated)


def test_deprecated_state_true_raises():
    with pytest.raises(NotImplementedError):
        Deprecated(state=True)


# -- HasAnyProperty --


def test_with_any_property_empty_raises():
    with pytest.raises(ValidationError):
        HasAnyProperty(properties=())


def test_with_any_property_set_semantics():
    assert HasAnyProperty(properties=(B, A)) == HasAnyProperty(properties=(A, B))


def test_with_any_property_dedupe():
    result = HasAnyProperty(properties=(A, A, B))
    assert len(result.properties) == 2


# -- MentionedIn --


def test_mentioned_in_axioms_empty_raises():
    with pytest.raises(ValidationError):
        MentionedIn(hashes=())


def test_mentioned_in_axioms_set_semantics():
    assert MentionedIn(hashes=(HASH_B, HASH_A)) == MentionedIn(hashes=(HASH_A, HASH_B))


def test_mentioned_in_axioms_dedupe():
    result = MentionedIn(hashes=(HASH_A, HASH_A, HASH_B))
    assert len(result.hashes) == 2


# -- InPositions --


def test_in_positions_empty_raises():
    with pytest.raises(ValidationError):
        InPositions(positions=())


def test_in_positions_set_semantics():
    assert InPositions(positions=(Position.RANGE, Position.DOMAIN)) == InPositions(
        positions=(Position.DOMAIN, Position.RANGE)
    )


def test_in_positions_dedupe():
    result = InPositions(positions=(Position.DOMAIN, Position.DOMAIN, Position.RANGE))
    assert len(result.positions) == 2


# -- InSelection --


def test_in_selection_holds_axiom_ref():
    ref = AxiomSelectionName("axioms:x")
    c = InSelection(ref=ref)
    assert c.ref == ref


def test_in_selection_holds_entity_ref():
    ref = EntitySelectionName("entities:x")
    c = InSelection(ref=ref)
    assert c.ref == ref


def test_in_selection_rejects_bare_string():
    with pytest.raises(ValidationError):
        InSelection(ref="not-a-typed-ref")  # pyright: ignore[reportArgumentType]


# -- AlwaysFalse --


def test_always_false_constructs():
    af = AlwaysFalse()
    assert isinstance(af, AlwaysFalse)


# -- Nullary variants are distinct by identity --


def test_nullary_variants_distinct():
    assert HasRole() != Deprecated(state=False)
    assert HasRole() != AlwaysFalse()
    assert Deprecated(state=False) != AlwaysFalse()


# -- WithTypes --


def test_of_types_empty_raises():
    with pytest.raises(ValidationError):
        WithTypes(tags=())


def test_of_types_set_semantics_order_insensitive():
    assert WithTypes(tags=(AxiomTag.SUB_CLASS_OF, AxiomTag.EQUIVALENT_CLASSES)) == WithTypes(
        tags=(AxiomTag.EQUIVALENT_CLASSES, AxiomTag.SUB_CLASS_OF)
    )


def test_of_types_dedupe():
    result = WithTypes(
        tags=(AxiomTag.SUB_CLASS_OF, AxiomTag.SUB_CLASS_OF, AxiomTag.EQUIVALENT_CLASSES)
    )
    assert len(result.tags) == 2
    assert set(result.tags) == {AxiomTag.SUB_CLASS_OF, AxiomTag.EQUIVALENT_CLASSES}


def test_of_types_rejects_unknown_tag():
    with pytest.raises(ValidationError):
        WithTypes(tags=("NotAnAxiomType",))  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


# -- MentionsAll --


def test_mentions_all_empty_raises():
    with pytest.raises(ValidationError):
        MentionsAll(iris=())


def test_mentions_all_set_semantics_order_insensitive():
    assert MentionsAll(iris=(B, A)) == MentionsAll(iris=(A, B))


def test_mentions_all_dedupe():
    result = MentionsAll(iris=(A, A, B))
    assert len(result.iris) == 2
    assert set(result.iris) == {A, B}


def test_mentions_all_nine_iris_raises():
    nine_iris = tuple(IRI(f":{i}") for i in range(9))

    with pytest.raises(ValidationError):
        MentionsAll(iris=nine_iris)


# -- MentionsAny --


def test_mentions_any_empty_raises():
    with pytest.raises(ValidationError):
        MentionsAny(iris=())


def test_mentions_any_set_semantics_order_insensitive():
    assert MentionsAny(iris=(B, A)) == MentionsAny(iris=(A, B))


def test_mentions_any_dedupe():
    result = MentionsAny(iris=(A, A, B))
    assert len(result.iris) == 2
    assert set(result.iris) == {A, B}
