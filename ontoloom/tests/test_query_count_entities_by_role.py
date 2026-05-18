"""Tests for the CountEntitiesByRole query."""

from collections import Counter

from ontoloom.axioms.store import add_axioms
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.types import PrefixName
from ontoloom.query.constraints import AlwaysFalse, InNamespaces, WithRoles
from ontoloom.query.count_entities_by_role import CountEntitiesByRole

# -- render snapshots: no DB --


def test_render_no_constraints():
    compiled = (CountEntitiesByRole(constraints=())).render()
    assert compiled.sql == (
        "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE 1 AND ae.role IS NOT NULL "
        "GROUP BY ae.role"
    )
    assert compiled.params == ()


def test_render_with_one_constraint():
    compiled = (CountEntitiesByRole(constraints=(WithRoles(roles=(EntityType.CLASS,)),))).render()
    assert compiled.sql == (
        "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE ae.role IN (?) AND ae.role IS NOT NULL "
        "GROUP BY ae.role"
    )
    assert compiled.params == (EntityType.CLASS,)


def test_render_always_false():
    # AlwaysFalse → WHERE 0 short-circuits the query; the role filter still
    # appears (SQLite folds `0 AND ...` to 0 — same plan, simpler render).
    compiled = (CountEntitiesByRole(constraints=(AlwaysFalse(),))).render()
    assert compiled.sql == (
        "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE 0 AND ae.role IS NOT NULL "
        "GROUP BY ae.role"
    )
    assert compiled.params == ()


def test_render_always_excludes_null_roles_and_groups():
    # Every rendered query must exclude role=NULL rows (either via the explicit
    # filter, or via WHERE 0 which returns no rows at all) and GROUP BY role.
    for q in [
        CountEntitiesByRole(constraints=()),
        CountEntitiesByRole(constraints=(WithRoles(roles=(EntityType.CLASS,)),)),
        CountEntitiesByRole(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),)),
        CountEntitiesByRole(constraints=(AlwaysFalse(),)),
    ]:
        sql = q.render().sql
        assert "ae.role IS NOT NULL" in sql or "WHERE 0" in sql
        assert "GROUP BY ae.role" in sql


# -- _run integration --


def test_run_empty_ontology(s):
    assert (CountEntitiesByRole(constraints=()))._run(s) == Counter()


def test_run_groups_by_role(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:hasOwner")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:hasParent")),
            Declaration(entity_type=EntityType.DATA_PROPERTY, iri=IRI("ex:age")),
            Declaration(entity_type=EntityType.NAMED_INDIVIDUAL, iri=IRI("ex:rex")),
        ],
    )

    result = (CountEntitiesByRole(constraints=()))._run(s)
    assert result == Counter(
        {
            EntityType.CLASS: 3,
            EntityType.OBJECT_PROPERTY: 2,
            EntityType.DATA_PROPERTY: 1,
            EntityType.NAMED_INDIVIDUAL: 1,
        }
    )


def test_run_returns_entity_type_keys(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = (CountEntitiesByRole(constraints=()))._run(s)
    assert len(result) == 1
    key = next(iter(result))
    assert isinstance(key, EntityType)
    assert key is EntityType.CLASS


def test_run_excludes_iris_appearing_only_in_non_role_positions(s):
    # `ex:Dog` is declared as a CLASS (role=CLASS) and ALSO appears as the
    # value of an rdfs:seeAlso annotation on the Cat declaration (role=None,
    # position=VALUE). The query must count Dog exactly once (under CLASS),
    # and `ex:OnlyAsAnnotationValue` — which appears ONLY as an annotation
    # value, never with a role — must not show up at all.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(
                entity_type=EntityType.CLASS,
                iri=IRI("ex:Cat"),
                annotations=(
                    Annotation(property=IRI("rdfs:seeAlso"), value=IRI("ex:Dog")),
                    Annotation(
                        property=IRI("rdfs:seeAlso"),
                        value=IRI("ex:OnlyAsAnnotationValue"),
                    ),
                ),
            ),
        ],
    )

    result = (CountEntitiesByRole(constraints=()))._run(s)
    # 2 classes (Dog, Cat). `ex:OnlyAsAnnotationValue` has no role so does
    # not appear under any key. `rdfs:seeAlso` carries role=ANNOTATION_PROPERTY.
    assert result[EntityType.CLASS] == 2
    assert result[EntityType.ANNOTATION_PROPERTY] == 1
    # No phantom entries for the role=None rows.
    assert all(v > 0 for v in result.values())
    # Specifically: `ex:OnlyAsAnnotationValue` is not surfaced anywhere.
    assert sum(result.values()) == 3  # Dog, Cat, rdfs:seeAlso


def test_run_filtered_by_namespace(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("other:Fish")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:hasOwner")),
        ],
    )

    result = CountEntitiesByRole(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),))._run(
        s
    )
    assert result == Counter({EntityType.CLASS: 1, EntityType.OBJECT_PROPERTY: 1})


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert (CountEntitiesByRole(constraints=(AlwaysFalse(),)))._run(s) == Counter()
