"""Tests for `undeclared_entity_count`.

Verifies the post-migration semantics: only IRIs that appear in entity-role
positions (i.e. carry a role in `axiom_entities`) are counted. IRIs that
appear only as annotation values (role=None) are excluded.
"""

from ontoloom.axioms.mutations import add_axioms
from ontoloom.entities.reader import undeclared_entity_count
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import AnnotationAssertion, Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import TypedLiteral
from ontoloom.owl.markers import EntityType


def test_undeclared_count_excludes_annotation_only_iris(s):
    # ex:Dog is declared (role=CLASS, has Declaration).
    # ex:Undeclared is referenced as a CLASS in SubClassOf (role=CLASS, no Declaration).
    # ex:OnlyAsAnnotationValue appears only as an rdfs:seeAlso value (role=None).
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            SubClassOf(sub_class=IRI("ex:Undeclared"), super_class=IRI("ex:Dog")),
            Declaration(
                entity_type=EntityType.CLASS,
                iri=IRI("ex:Cat"),
                annotations=(
                    Annotation(
                        property=IRI("rdfs:seeAlso"),
                        value=IRI("ex:OnlyAsAnnotationValue"),
                    ),
                ),
            ),
        ],
    )

    # Only ex:Undeclared satisfies (HasRole AND no Declaration).
    # ex:OnlyAsAnnotationValue has role=None, so it is excluded.
    assert undeclared_entity_count(s) == 1


def test_undeclared_count_excludes_annotation_assertion_value_iri(s):
    # ex:Dog is declared; the annotation assertion's value `ex:Referenced` lives
    # in a value position (role=None) — it must NOT be counted as undeclared.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            AnnotationAssertion(
                property=IRI("rdfs:seeAlso"),
                subject=IRI("ex:Dog"),
                value=IRI("ex:Referenced"),
            ),
        ],
    )

    # ex:Dog: declared. ex:Referenced: role=None (annotation value). rdfs:seeAlso:
    # appears as an annotation property (role=ANNOTATION_PROPERTY) but is
    # undeclared. Expected count: 1 (rdfs:seeAlso only).
    assert undeclared_entity_count(s) == 1


def test_undeclared_count_zero_when_all_role_iris_declared(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
        ],
    )

    assert undeclared_entity_count(s) == 0


def test_undeclared_count_deprecated_excluded_by_default(s):
    # ex:Undeclared has role=CLASS (from SubClassOf), no Declaration, and an
    # owl:deprecated "true" annotation. With exclude_deprecated=True it is
    # filtered out; with False it shows up. We also declare owl:deprecated as
    # an annotation property so it doesn't itself appear in the count.
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(
                entity_type=EntityType.ANNOTATION_PROPERTY,
                iri=IRI("owl:deprecated"),
            ),
            SubClassOf(sub_class=IRI("ex:Undeclared"), super_class=IRI("ex:Dog")),
            AnnotationAssertion(
                property=IRI("owl:deprecated"),
                subject=IRI("ex:Undeclared"),
                value=TypedLiteral(value="true"),
            ),
        ],
    )

    # By default the deprecated entity is excluded.
    assert undeclared_entity_count(s, exclude_deprecated=True) == 0
    # Including deprecated should surface it.
    assert undeclared_entity_count(s, exclude_deprecated=False) == 1
