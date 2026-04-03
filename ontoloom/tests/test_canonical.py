"""Tests for canonical normalization and logical-only content hashing."""

from ontoloom.core.ontology.canonical import canonical_dump, content_hash
from ontoloom.core.ontology.models.assertions import DifferentIndividuals, SameIndividual
from ontoloom.core.ontology.models.axioms import (
    DisjointClasses,
    EquivalentClasses,
    EquivalentDataProperties,
    EquivalentObjectProperties,
    HasKey,
    SubClassOf,
)
from ontoloom.core.ontology.models.expressions import (
    NamedClass,
    ObjectIntersectionOf,
    ObjectSomeValuesFrom,
)
from ontoloom.core.ontology.models.literals import IRI, Annotation, LangLiteral

# -- Annotation exclusion --


def test_annotations_excluded_from_canonical_dump():
    a1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    a2 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
        annotations=(
            Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="important")),
        ),
    )
    assert canonical_dump(a1) == canonical_dump(a2)


def test_content_hash_stable_across_annotations():
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax2 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
        annotations=(Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note")),),
    )
    assert content_hash(ax1) == content_hash(ax2)


def test_content_hash_different_for_different_content():
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax2 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Cat")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    assert content_hash(ax1) != content_hash(ax2)


# -- Set-semantic sorting: axiom-level --


def test_equivalent_classes_order_irrelevant():
    a, b, c = IRI("ex:A"), IRI("ex:B"), IRI("ex:C")
    ax1 = EquivalentClasses(expressions=(NamedClass(iri=a), NamedClass(iri=b), NamedClass(iri=c)))
    ax2 = EquivalentClasses(expressions=(NamedClass(iri=c), NamedClass(iri=a), NamedClass(iri=b)))
    assert canonical_dump(ax1) == canonical_dump(ax2)


def test_disjoint_classes_order_irrelevant():
    ax1 = DisjointClasses(expressions=(NamedClass(iri=IRI("ex:A")), NamedClass(iri=IRI("ex:B"))))
    ax2 = DisjointClasses(expressions=(NamedClass(iri=IRI("ex:B")), NamedClass(iri=IRI("ex:A"))))
    assert canonical_dump(ax1) == canonical_dump(ax2)


def test_equivalent_object_properties_order_irrelevant():
    ax1 = EquivalentObjectProperties(properties=(IRI("ex:p"), IRI("ex:q"), IRI("ex:r")))
    ax2 = EquivalentObjectProperties(properties=(IRI("ex:r"), IRI("ex:p"), IRI("ex:q")))
    assert canonical_dump(ax1) == canonical_dump(ax2)


def test_equivalent_data_properties_order_irrelevant():
    ax1 = EquivalentDataProperties(properties=(IRI("ex:dp1"), IRI("ex:dp2")))
    ax2 = EquivalentDataProperties(properties=(IRI("ex:dp2"), IRI("ex:dp1")))
    assert canonical_dump(ax1) == canonical_dump(ax2)


def test_same_individual_order_irrelevant():
    ax1 = SameIndividual(individuals=(IRI("ex:a"), IRI("ex:b")))
    ax2 = SameIndividual(individuals=(IRI("ex:b"), IRI("ex:a")))
    assert canonical_dump(ax1) == canonical_dump(ax2)


def test_different_individuals_order_irrelevant():
    ax1 = DifferentIndividuals(individuals=(IRI("ex:a"), IRI("ex:b"), IRI("ex:c")))
    ax2 = DifferentIndividuals(individuals=(IRI("ex:c"), IRI("ex:a"), IRI("ex:b")))
    assert canonical_dump(ax1) == canonical_dump(ax2)


def test_has_key_properties_order_irrelevant():
    ax1 = HasKey(
        class_expression=NamedClass(iri=IRI("ex:Person")),
        object_properties=(IRI("ex:p1"), IRI("ex:p2")),
        data_properties=(IRI("ex:d1"), IRI("ex:d2")),
    )
    ax2 = HasKey(
        class_expression=NamedClass(iri=IRI("ex:Person")),
        object_properties=(IRI("ex:p2"), IRI("ex:p1")),
        data_properties=(IRI("ex:d2"), IRI("ex:d1")),
    )
    assert canonical_dump(ax1) == canonical_dump(ax2)


# -- Set-semantic sorting: expression-level (recursive) --


def test_intersection_operands_sorted():
    a = NamedClass(iri=IRI("ex:A"))
    b = NamedClass(iri=IRI("ex:B"))
    expr1 = ObjectIntersectionOf(operands=(a, b))
    expr2 = ObjectIntersectionOf(operands=(b, a))
    ax1 = SubClassOf(sub_class=NamedClass(iri=IRI("ex:X")), super_class=expr1)
    ax2 = SubClassOf(sub_class=NamedClass(iri=IRI("ex:X")), super_class=expr2)
    assert canonical_dump(ax1) == canonical_dump(ax2)


def test_deeply_nested_normalization():
    a = NamedClass(iri=IRI("ex:A"))
    b = NamedClass(iri=IRI("ex:B"))
    c = NamedClass(iri=IRI("ex:C"))
    p = IRI("ex:p")

    inter_ba = ObjectIntersectionOf(operands=(b, a))
    inter_ab = ObjectIntersectionOf(operands=(a, b))
    some_pc = ObjectSomeValuesFrom(property=p, filler=c)

    ax1 = EquivalentClasses(expressions=(inter_ba, some_pc))
    ax2 = EquivalentClasses(expressions=(some_pc, inter_ab))
    assert canonical_dump(ax1) == canonical_dump(ax2)


# -- Order-sensitive fields preserved --


def test_subclassof_order_preserved():
    a = NamedClass(iri=IRI("ex:A"))
    b = NamedClass(iri=IRI("ex:B"))
    ax1 = SubClassOf(sub_class=a, super_class=b)
    ax2 = SubClassOf(sub_class=b, super_class=a)
    assert canonical_dump(ax1) != canonical_dump(ax2)
