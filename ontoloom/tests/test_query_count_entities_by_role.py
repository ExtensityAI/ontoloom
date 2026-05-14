"""Tests for the CountEntitiesByRole query."""

from collections import Counter

from ontoloom.axioms.store import add_axioms
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.types import PrefixName
from ontoloom.query._constraints import AlwaysFalse, InNamespaces, WithRoles
from ontoloom.query.count_entities_by_role import CountEntitiesByRole, _run, render

# -- render snapshots: no DB --


def test_render_no_constraints():
    compiled = render(CountEntitiesByRole(constraints=()))
    assert compiled.sql == (
        "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE 1 AND ae.role IS NOT NULL "
        "GROUP BY ae.role"
    )
    assert compiled.params == ()


def test_render_with_one_constraint():
    compiled = render(CountEntitiesByRole(constraints=(WithRoles(roles=(EntityType.CLASS,)),)))
    assert compiled.sql == (
        "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE ae.role IN (?) AND ae.role IS NOT NULL "
        "GROUP BY ae.role"
    )
    assert compiled.params == (EntityType.CLASS,)


def test_render_always_false():
    compiled = render(CountEntitiesByRole(constraints=(AlwaysFalse(),)))
    assert compiled.sql == (
        "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
        "WHERE 0 AND ae.role IS NOT NULL "
        "GROUP BY ae.role"
    )
    assert compiled.params == ()


def test_render_always_has_role_not_null_and_group_by():
    # Every snapshot must contain the unconditional role-guard and GROUP BY.
    for q in [
        CountEntitiesByRole(constraints=()),
        CountEntitiesByRole(constraints=(WithRoles(roles=(EntityType.CLASS,)),)),
        CountEntitiesByRole(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),)),
        CountEntitiesByRole(constraints=(AlwaysFalse(),)),
    ]:
        sql = render(q).sql
        assert "AND ae.role IS NOT NULL" in sql
        assert "GROUP BY ae.role" in sql


# -- _run integration --


def test_run_empty_ontology(s):
    assert _run(s, CountEntitiesByRole(constraints=())) == Counter()


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

    result = _run(s, CountEntitiesByRole(constraints=()))
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
    result = _run(s, CountEntitiesByRole(constraints=()))
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

    result = _run(s, CountEntitiesByRole(constraints=()))
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

    result = _run(
        s,
        CountEntitiesByRole(constraints=(InNamespaces(namespaces=(PrefixName("ex"),)),)),
    )
    assert result == Counter({EntityType.CLASS: 1, EntityType.OBJECT_PROPERTY: 1})


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert _run(s, CountEntitiesByRole(constraints=(AlwaysFalse(),))) == Counter()
