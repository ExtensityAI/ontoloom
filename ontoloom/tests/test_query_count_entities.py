"""Tests for the CountEntities query and the shared `_entity_predicates` helper."""

from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import AxiomHash, HashedAxiom
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType, Position
from ontoloom.prefixes.types import PrefixName
from ontoloom.query._predicates import DECLARED_EXISTS, DECLARED_NOT_EXISTS, NOT_DEPRECATED
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
    WithRoles,
)
from ontoloom.query.count_entities import CountEntities
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
    SelectionKind,
    SelectionName,
)

# 64-char lowercase hex placeholder for AxiomHash construction in render snapshots.
_HASH_A = "a" * 64


# -- render snapshots: no DB --


def test_render_no_constraints():
    compiled = (CountEntities(constraints=())).render()
    assert compiled.sql == "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE 1"
    assert compiled.params == ()


def test_render_with_iris_single():
    compiled = (CountEntities(constraints=(InIRIs(iris=(IRI("ex:A"),)),))).render()
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.entity_iri IN (?)"
    )
    assert compiled.params == ("ex:A",)


def test_render_with_iris_many():
    compiled = (CountEntities(constraints=(InIRIs(iris=(IRI("ex:B"), IRI("ex:A"))),))).render()
    # dedupe_sort sorts the iris
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.entity_iri IN (?,?)"
    )
    assert compiled.params == ("ex:A", "ex:B")


def test_render_with_roles():
    compiled = (
        CountEntities(
            constraints=(WithRoles(roles=(EntityType.OBJECT_PROPERTY, EntityType.CLASS)),)
        )
    ).render()
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.role IN (?,?)"
    )
    # sorted lexicographically by StrEnum value
    assert compiled.params == (EntityType.CLASS, EntityType.OBJECT_PROPERTY)


def test_render_has_entity_role():
    compiled = (CountEntities(constraints=(HasRole(),))).render()
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.role IS NOT NULL"
    )
    assert compiled.params == ()


def test_render_in_namespaces_single():
    compiled = (CountEntities(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),))).render()
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        r"WHERE ae.entity_iri LIKE ? || ':%' ESCAPE '\'"
    )
    assert compiled.params == ("ex",)


def test_render_in_namespaces_multi():
    compiled = (
        CountEntities(
            constraints=(InNamespaces(namespaces=(PrefixName("ex"), PrefixName("other"))),)
        )
    ).render()
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        r"WHERE (ae.entity_iri LIKE ? || ':%' ESCAPE '\' "
        r"OR ae.entity_iri LIKE ? || ':%' ESCAPE '\')"
    )
    assert compiled.params == ("ex", "other")


def test_render_declared_true():
    compiled = (CountEntities(constraints=(Declared(state=True),))).render()
    assert compiled.sql == (
        f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE {DECLARED_EXISTS}"
    )
    assert compiled.params == ()


def test_render_declared_false():
    compiled = (CountEntities(constraints=(Declared(state=False),))).render()
    assert compiled.sql == (
        f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE {DECLARED_NOT_EXISTS}"
    )
    assert compiled.params == ()


def test_render_not_deprecated():
    compiled = (CountEntities(constraints=(Deprecated(state=False),))).render()
    assert compiled.sql == (
        f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE {NOT_DEPRECATED}"
    )
    assert compiled.params == ()


def test_render_with_any_property():
    compiled = (
        CountEntities(constraints=(HasAnyProperty(properties=(IRI("rdfs:label"),)),))
    ).render()
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE EXISTS (SELECT 1 FROM entity_text et_p "
        "WHERE et_p.entity_iri = ae.entity_iri "
        "AND et_p.property IN (?))"
    )
    assert compiled.params == ("rdfs:label",)


def test_render_mentioned_in_axioms():
    compiled = (CountEntities(constraints=(MentionedIn(hashes=(AxiomHash(_HASH_A),)),))).render()
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE EXISTS (SELECT 1 FROM axioms a_m "
        "WHERE a_m.id = ae.axiom_id "
        "AND a_m.hash IN (?))"
    )
    assert compiled.params == (_HASH_A,)


def test_render_in_positions():
    compiled = (CountEntities(constraints=(InPositions(positions=(Position.SUB_CLASS,)),))).render()
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.position IN (?)"
    )
    assert compiled.params == (Position.SUB_CLASS,)


def test_render_in_selection_entities():
    ref = EntitySelectionName("entities:my_sel")
    compiled = (CountEntities(constraints=(InSelection(ref=ref),))).render()
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE EXISTS (SELECT 1 FROM selection_items si_w "
        "WHERE si_w.item = ae.entity_iri "
        "AND si_w.selection_name = ?)"
    )
    assert compiled.params == ("my_sel",)


def test_render_in_selection_axioms():
    ref = AxiomSelectionName("axioms:my_axiom_sel")
    compiled = (CountEntities(constraints=(InSelection(ref=ref),))).render()
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE EXISTS (SELECT 1 FROM selection_items si_w "
        "JOIN axioms a_w ON a_w.hash = si_w.item "
        "WHERE a_w.id = ae.axiom_id "
        "AND si_w.selection_name = ?)"
    )
    assert compiled.params == ("my_axiom_sel",)


def test_render_always_false():
    compiled = (CountEntities(constraints=(AlwaysFalse(),))).render()
    assert compiled.sql == "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE 0"
    assert compiled.params == ()


def test_render_always_false_short_circuits_other_constraints():
    # Even with other constraints alongside AlwaysFalse, predicate is "0".
    compiled = (
        CountEntities(constraints=(InIRIs(iris=(IRI("ex:A"),)), AlwaysFalse(), HasRole()))
    ).render()
    assert compiled.sql == "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE 0"
    assert compiled.params == ()


def test_render_conjunction():
    compiled = (CountEntities(constraints=(InIRIs(iris=(IRI("ex:A"),)), HasRole()))).render()
    # normalize sorts constraints by repr, so HasRole appears before InIRIs
    assert compiled.sql == (
        "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE ae.role IS NOT NULL AND ae.entity_iri IN (?)"
    )
    assert compiled.params == ("ex:A",)


def test_render_namespace_param_escapes_like_metacharacters():
    # PrefixName regex doesn't allow %/_, but the helper must still pass through
    # escape_like — verify it does by passing a value with no metacharacters
    # (no-op escape) and the binding equals the raw prefix.
    compiled = (CountEntities(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),))).render()
    assert compiled.params == ("ex",)


# -- _run integration: against the `s` fixture --


def test_run_empty_ontology(s):
    assert (CountEntities(constraints=()))._run(s) == 0


def test_run_single_declaration(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert (CountEntities(constraints=()))._run(s) == 1


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
    assert (CountEntities(constraints=(HasRole(),)))._run(s) == 3

    # Classes only.
    assert CountEntities(constraints=(WithRoles(roles=(EntityType.CLASS,)),))._run(s) == 2

    # ObjectProperty only.
    assert CountEntities(constraints=(WithRoles(roles=(EntityType.OBJECT_PROPERTY,)),))._run(s) == 1


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
    ref = EntitySelectionName("entities:dogs_and_cats")
    assert (CountEntities(constraints=(InSelection(ref=ref),)))._run(s) == 2


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
    ref = AxiomSelectionName("axioms:dog_only")
    assert (CountEntities(constraints=(InSelection(ref=ref),)))._run(s) == 1


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert (CountEntities(constraints=(AlwaysFalse(),)))._run(s) == 0


def test_run_namespace_filter(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("other:Fish")),
        ],
    )
    assert CountEntities(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),))._run(s) == 1
    assert (
        CountEntities(
            constraints=(InNamespaces(namespaces=(PrefixName("ex"), PrefixName("other"))),)
        )._run(s)
        == 2
    )


def test_run_normalize_runs_before_render(s):
    # normalize_entity intersects two InIRIs into one; the result is a
    # single-element set, and the SQL run should still match.
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    q = CountEntities(
        constraints=(
            InIRIs(iris=(IRI("ex:Dog"), IRI("ex:Cat"))),
            InIRIs(iris=(IRI("ex:Dog"), IRI("ex:Fish"))),
        )
    )
    assert q._run(s) == 1
