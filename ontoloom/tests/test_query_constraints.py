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
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.selections.types import SelectionKind, SelectionKindError
from pydantic import ValidationError

# -- Helpers --

A = IRI(":A")
B = IRI(":B")
C = IRI(":C")

HASH_A = AxiomHash("a" * 64)
HASH_B = AxiomHash("b" * 64)
HASH_C = AxiomHash("c" * 64)


# -- WithIRIs --


def test_with_iris_empty_raises():
    with pytest.raises(ValidationError):
        WithIRIs(iris=())


def test_with_iris_set_semantics_order_insensitive():
    assert WithIRIs(iris=(B, A)) == WithIRIs(iris=(A, B))


def test_with_iris_dedupe():
    result = WithIRIs(iris=(A, A, B))
    assert len(result.iris) == 2
    assert set(result.iris) == {A, B}


def test_with_iris_sorted():
    result = WithIRIs(iris=(B, A))
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


# -- HasEntityRole --


def test_has_entity_role_constructs():
    r = HasEntityRole()
    assert isinstance(r, HasEntityRole)


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


# -- NotDeprecated --


def test_not_deprecated_constructs():
    nd = NotDeprecated()
    assert isinstance(nd, NotDeprecated)


# -- WithAnyProperty --


def test_with_any_property_empty_raises():
    with pytest.raises(ValidationError):
        WithAnyProperty(properties=())


def test_with_any_property_set_semantics():
    assert WithAnyProperty(properties=(B, A)) == WithAnyProperty(properties=(A, B))


def test_with_any_property_dedupe():
    result = WithAnyProperty(properties=(A, A, B))
    assert len(result.properties) == 2


# -- MentionedInAxioms --


def test_mentioned_in_axioms_empty_raises():
    with pytest.raises(ValidationError):
        MentionedInAxioms(hashes=())


def test_mentioned_in_axioms_set_semantics():
    assert MentionedInAxioms(hashes=(HASH_B, HASH_A)) == MentionedInAxioms(hashes=(HASH_A, HASH_B))


def test_mentioned_in_axioms_dedupe():
    result = MentionedInAxioms(hashes=(HASH_A, HASH_A, HASH_B))
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


def test_in_selection_no_expected_kind_axioms():
    ref = ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name="x")
    c = InSelection(ref=ref)
    assert c.ref is ref
    assert c.expected_kind is None


def test_in_selection_no_expected_kind_entities():
    ref = ResolvedSelection(kind=SelectionKind.ENTITIES, bare_name="x")
    c = InSelection(ref=ref)
    assert c.expected_kind is None


def test_in_selection_matching_expected_kind():
    ref = ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name="x")
    c = InSelection(ref=ref, expected_kind=SelectionKind.AXIOMS)
    assert c.expected_kind == SelectionKind.AXIOMS


def test_in_selection_kind_mismatch_raises():
    ref = ResolvedSelection(kind=SelectionKind.ENTITIES, bare_name="x")

    with pytest.raises(SelectionKindError):
        InSelection(ref=ref, expected_kind=SelectionKind.AXIOMS)


def test_in_selection_kind_mismatch_other_direction_raises():
    ref = ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name="x")

    with pytest.raises(SelectionKindError):
        InSelection(ref=ref, expected_kind=SelectionKind.ENTITIES)


# -- AlwaysFalse --


def test_always_false_constructs():
    af = AlwaysFalse()
    assert isinstance(af, AlwaysFalse)


# -- Nullary variants are distinct by identity --


def test_nullary_variants_distinct():
    assert HasEntityRole() != NotDeprecated()
    assert HasEntityRole() != AlwaysFalse()
    assert NotDeprecated() != AlwaysFalse()


# -- OfTypes --


def test_of_types_empty_raises():
    with pytest.raises(ValidationError):
        OfTypes(tags=())


def test_of_types_set_semantics_order_insensitive():
    assert OfTypes(tags=("SubClassOf", "EquivalentClasses")) == OfTypes(
        tags=("EquivalentClasses", "SubClassOf")
    )


def test_of_types_dedupe():
    result = OfTypes(tags=("SubClassOf", "SubClassOf", "EquivalentClasses"))
    assert len(result.tags) == 2
    assert set(result.tags) == {"SubClassOf", "EquivalentClasses"}


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
