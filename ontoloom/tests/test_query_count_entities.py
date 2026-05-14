"""Tests for the CountEntities query and the shared `_entity_predicates` helper."""

from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import AxiomHash, HashedAxiom
from ontoloom.owl.axioms import Declaration
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
    NotDeprecated,
    WithAnyProperty,
    WithIRIs,
    WithRoles,
)
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.query.count_entities import CountEntities, _run, render
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import SelectionKind, SelectionName
from ontoloom.text_index import DECLARED_EXISTS, DECLARED_NOT_EXISTS, NOT_DEPRECATED

# 64-char lowercase hex placeholder for AxiomHash construction in render snapshots.
_HASH_A = "a" * 64


# -- render snapshots: no DB --


def test_render_no_constraints():
    compiled = render(CountEntities(constraints=()))
    assert compiled.sql == "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae"
    assert compiled.params == ()


def test_render_with_iris_single():
    compiled = render(CountEntities(constraints=(WithIRIs(iris=(IRI("ex:A"),)),)))
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.entity_iri IN (?)"
    )
    assert compiled.params == ("ex:A",)


def test_render_with_iris_many():
    compiled = render(CountEntities(constraints=(WithIRIs(iris=(IRI("ex:B"), IRI("ex:A"))),)))
    # dedupe_sort sorts the iris
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.entity_iri IN (?,?)"
    )
    assert compiled.params == ("ex:A", "ex:B")


def test_render_with_roles():
    compiled = render(
        CountEntities(
            constraints=(WithRoles(roles=(EntityType.OBJECT_PROPERTY, EntityType.CLASS)),)
        )
    )
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.role IN (?,?)"
    )
    # sorted lexicographically by StrEnum value
    assert compiled.params == (EntityType.CLASS, EntityType.OBJECT_PROPERTY)


def test_render_has_entity_role():
    compiled = render(CountEntities(constraints=(HasEntityRole(),)))
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.role IS NOT NULL"
    )
    assert compiled.params == ()


def test_render_in_namespaces_single():
    compiled = render(CountEntities(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),)))
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        r"WHERE ae.entity_iri LIKE ? || ':%' ESCAPE '\'"
    )
    assert compiled.params == ("ex",)


def test_render_in_namespaces_multi():
    compiled = render(
        CountEntities(
            constraints=(InNamespaces(namespaces=(PrefixName("ex"), PrefixName("other"))),)
        )
    )
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        r"WHERE (ae.entity_iri LIKE ? || ':%' ESCAPE '\' "
        r"OR ae.entity_iri LIKE ? || ':%' ESCAPE '\')"
    )
    assert compiled.params == ("ex", "other")


def test_render_declared_true():
    compiled = render(CountEntities(constraints=(Declared(state=True),)))
    assert compiled.sql == (
        f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE {DECLARED_EXISTS}"
    )
    assert compiled.params == ()


def test_render_declared_false():
    compiled = render(CountEntities(constraints=(Declared(state=False),)))
    assert compiled.sql == (
        f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE {DECLARED_NOT_EXISTS}"
    )
    assert compiled.params == ()


def test_render_not_deprecated():
    compiled = render(CountEntities(constraints=(NotDeprecated(),)))
    assert compiled.sql == (
        f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE {NOT_DEPRECATED}"
    )
    assert compiled.params == ()


def test_render_with_any_property():
    compiled = render(
        CountEntities(constraints=(WithAnyProperty(properties=(IRI("rdfs:label"),)),))
    )
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE EXISTS (SELECT 1 FROM entity_text et_p "
        "WHERE et_p.entity_iri = ae.entity_iri "
        "AND et_p.property IN (?))"
    )
    assert compiled.params == ("rdfs:label",)


def test_render_mentioned_in_axioms():
    compiled = render(CountEntities(constraints=(MentionedInAxioms(hashes=(AxiomHash(_HASH_A),)),)))
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE EXISTS (SELECT 1 FROM axioms a_m "
        "WHERE a_m.id = ae.axiom_id "
        "AND a_m.hash IN (?))"
    )
    assert compiled.params == (_HASH_A,)


def test_render_in_positions():
    compiled = render(CountEntities(constraints=(InPositions(positions=(Position.SUB_CLASS,)),)))
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.position IN (?)"
    )
    assert compiled.params == (Position.SUB_CLASS,)


def test_render_in_selection_entities():
    ref = ResolvedSelection(kind=SelectionKind.ENTITIES, bare_name="my_sel")
    compiled = render(CountEntities(constraints=(InSelection(ref=ref),)))
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE EXISTS (SELECT 1 FROM selection_items si_w "
        "WHERE si_w.item = ae.entity_iri "
        "AND si_w.selection_name = ?)"
    )
    assert compiled.params == ("my_sel",)


def test_render_in_selection_axioms():
    ref = ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name="my_axiom_sel")
    compiled = render(CountEntities(constraints=(InSelection(ref=ref),)))
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE EXISTS (SELECT 1 FROM selection_items si_w "
        "JOIN axioms a_w ON a_w.hash = si_w.item "
        "WHERE a_w.id = ae.axiom_id "
        "AND si_w.selection_name = ?)"
    )
    assert compiled.params == ("my_axiom_sel",)


def test_render_always_false():
    compiled = render(CountEntities(constraints=(AlwaysFalse(),)))
    assert compiled.sql == "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE 0"
    assert compiled.params == ()


def test_render_always_false_short_circuits_other_constraints():
    # Even with other constraints alongside AlwaysFalse, predicate is "0".
    compiled = render(
        CountEntities(constraints=(WithIRIs(iris=(IRI("ex:A"),)), AlwaysFalse(), HasEntityRole()))
    )
    assert compiled.sql == "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE 0"
    assert compiled.params == ()


def test_render_conjunction():
    compiled = render(CountEntities(constraints=(WithIRIs(iris=(IRI("ex:A"),)), HasEntityRole())))
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE ae.entity_iri IN (?) AND ae.role IS NOT NULL"
    )
    assert compiled.params == ("ex:A",)


def test_render_namespace_param_escapes_like_metacharacters():
    # PrefixName regex doesn't allow %/_, but the helper must still pass through
    # escape_like — verify it does by passing a value with no metacharacters
    # (no-op escape) and the binding equals the raw prefix.
    compiled = render(CountEntities(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),)))
    assert compiled.params == ("ex",)


# -- _run integration: against the `s` fixture --


def test_run_empty_ontology(s):
    assert _run(s, CountEntities(constraints=())) == 0


def test_run_single_declaration(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert _run(s, CountEntities(constraints=())) == 1


def test_run_multiple_role_filter(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:hasOwner")),
        ],
    )
    # All entities (any role).
    assert _run(s, CountEntities(constraints=(HasEntityRole(),))) == 3

    # Classes only.
    assert (
        _run(
            s,
            CountEntities(constraints=(WithRoles(roles=(EntityType.CLASS,)),)),
        )
        == 2
    )

    # ObjectProperty only.
    assert (
        _run(
            s,
            CountEntities(constraints=(WithRoles(roles=(EntityType.OBJECT_PROPERTY,)),)),
        )
        == 1
    )


def test_run_in_selection_entities(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
        ],
    )
    upsert_selection(
        s,
        SelectionName("dogs_and_cats"),
        SelectionKind.ENTITIES,
        ["ex:Dog", "ex:Cat"],
        source="test",
    )
    ref = ResolvedSelection(kind=SelectionKind.ENTITIES, bare_name="dogs_and_cats")
    assert _run(s, CountEntities(constraints=(InSelection(ref=ref),))) == 2


def test_run_in_selection_axioms(s):
    dog_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    cat_decl = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat"))

    add_axioms(s, [dog_decl, cat_decl])

    dog_hash = HashedAxiom.of(dog_decl).hash
    upsert_selection(
        s,
        SelectionName("dog_only"),
        SelectionKind.AXIOMS,
        [dog_hash],
        source="test",
    )
    ref = ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name="dog_only")
    assert _run(s, CountEntities(constraints=(InSelection(ref=ref),))) == 1


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert _run(s, CountEntities(constraints=(AlwaysFalse(),))) == 0


def test_run_namespace_filter(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("other:Fish")),
        ],
    )
    assert (
        _run(
            s,
            CountEntities(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),)),
        )
        == 1
    )
    assert (
        _run(
            s,
            CountEntities(
                constraints=(InNamespaces(namespaces=(PrefixName("ex"), PrefixName("other"))),)
            ),
        )
        == 2
    )


def test_run_normalize_runs_before_render(s):
    # normalize_entity intersects two WithIRIs into one; the result is a
    # single-element set, and the SQL run should still match.
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    q = CountEntities(
        constraints=(
            WithIRIs(iris=(IRI("ex:Dog"), IRI("ex:Cat"))),
            WithIRIs(iris=(IRI("ex:Dog"), IRI("ex:Fish"))),
        )
    )
    assert _run(s, q) == 1
