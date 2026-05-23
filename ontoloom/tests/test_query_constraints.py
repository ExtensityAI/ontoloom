import pytest
from ontoloom.axioms.hashing import AxiomHash
from ontoloom.owl.axioms import AxiomTag
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType, Position
from ontoloom.prefixes.types import PrefixName
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


# -- Parametrized: empty/order-insensitive/dedupe across simple tuple constraints --

_SIMPLE_TUPLE_CONSTRAINTS = [
    (InIRIs, "iris", (A, B)),
    (WithRoles, "roles", (EntityType.CLASS, EntityType.NAMED_INDIVIDUAL)),
    (InNamespaces, "namespaces", (PrefixName("owl"), PrefixName("rdfs"))),
    (InPositions, "positions", (Position.DOMAIN, Position.RANGE)),
    (HasAnyProperty, "properties", (A, B)),
    (MentionedIn, "hashes", (HASH_A, HASH_B)),
    (WithTypes, "tags", (AxiomTag.SUB_CLASS_OF, AxiomTag.EQUIVALENT_CLASSES)),
    (MentionsAll, "iris", (A, B)),
    (MentionsAny, "iris", (A, B)),
]


@pytest.mark.parametrize("cls, field, sample", _SIMPLE_TUPLE_CONSTRAINTS)
def test_empty_raises(cls, field, sample):
    del sample
    with pytest.raises(ValidationError):
        cls(**{field: ()})


@pytest.mark.parametrize("cls, field, sample", _SIMPLE_TUPLE_CONSTRAINTS)
def test_set_semantics_order_insensitive(cls, field, sample):
    x, y = sample
    assert cls(**{field: (y, x)}) == cls(**{field: (x, y)})


@pytest.mark.parametrize("cls, field, sample", _SIMPLE_TUPLE_CONSTRAINTS)
def test_dedupe(cls, field, sample):
    x, y = sample
    result = cls(**{field: (x, x, y)})
    values = getattr(result, field)
    assert len(values) == 2
    assert set(values) == {x, y}


# -- InIRIs sort order --


def test_with_iris_sorted():
    result = InIRIs(iris=(B, A))
    assert result.iris == tuple(sorted({A, B}))


# -- HasRole / AlwaysFalse / nullary identity --


def test_has_entity_role_constructs():
    assert isinstance(HasRole(), HasRole)


def test_always_false_constructs():
    assert isinstance(AlwaysFalse(), AlwaysFalse)


def test_nullary_variants_distinct():
    assert HasRole() != Deprecated(state=False)
    assert HasRole() != AlwaysFalse()
    assert Deprecated(state=False) != AlwaysFalse()


# -- Declared --


def test_declared_true():
    assert Declared(state=True).state is True


def test_declared_false():
    assert Declared(state=False).state is False


def test_declared_no_default_raises():
    with pytest.raises(ValidationError):
        Declared()  # pyright: ignore[reportCallIssue]


# -- Deprecated --


def test_deprecated_state_false_constructs():
    assert isinstance(Deprecated(state=False), Deprecated)


def test_deprecated_state_true_raises():
    with pytest.raises(NotImplementedError):
        Deprecated(state=True)


# -- InAxiomSelection / InEntitySelection --


def test_in_axiom_selection_holds_axiom_ref():
    ref = AxiomSelectionName("axioms:x")
    assert InAxiomSelection(name=ref).name == ref


def test_in_entity_selection_holds_entity_ref():
    ref = EntitySelectionName("entities:x")
    assert InEntitySelection(name=ref).name == ref


def test_in_axiom_selection_rejects_bare_string():
    with pytest.raises(ValidationError):
        InAxiomSelection(name="not-a-typed-ref")  # pyright: ignore[reportArgumentType]


def test_in_entity_selection_rejects_bare_string():
    with pytest.raises(ValidationError):
        InEntitySelection(name="not-a-typed-ref")  # pyright: ignore[reportArgumentType]


def test_in_axiom_selection_rejects_entity_ref():
    with pytest.raises(ValidationError):
        InAxiomSelection(name=EntitySelectionName("entities:x"))  # pyright: ignore[reportArgumentType]


def test_in_entity_selection_rejects_axiom_ref():
    with pytest.raises(ValidationError):
        InEntitySelection(name=AxiomSelectionName("axioms:x"))  # pyright: ignore[reportArgumentType]


# -- WithTypes: unknown tag rejection --


def test_of_types_rejects_unknown_tag():
    with pytest.raises(ValidationError):
        WithTypes(tags=("NotAnAxiomType",))  # type: ignore[arg-type]


# -- MentionsAll: IRI count cap --


def test_mentions_all_nine_iris_raises():
    nine_iris = tuple(IRI(f":{i}") for i in range(9))

    with pytest.raises(ValidationError):
        MentionsAll(iris=nine_iris)


# -- HasAnyAnnotation --


def test_has_any_annotation_empty_raises():
    with pytest.raises(ValidationError):
        HasAnyAnnotation(properties=())


def test_has_any_annotation_properties_sorted_and_deduped():
    assert HasAnyAnnotation(properties=(IRI("ex:b"), IRI("ex:a"), IRI("ex:a"))).properties == (
        IRI("ex:a"),
        IRI("ex:b"),
    )
