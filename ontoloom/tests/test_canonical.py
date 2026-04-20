from ontoloom.ontology.canonical import axiom_hash, canonical_json
from ontoloom.ontology.models.assertions import DifferentIndividuals, SameIndividual
from ontoloom.ontology.models.axioms import (
    DataPropertyRange,
    DatatypeDefinition,
    DisjointClasses,
    EquivalentClasses,
    EquivalentDataProperties,
    EquivalentObjectProperties,
    HasKey,
    SubClassOf,
)
from ontoloom.ontology.models.expressions import (
    DataSomeValuesFrom,
    NamedClass,
    ObjectIntersectionOf,
    ObjectSomeValuesFrom,
)
from ontoloom.ontology.models.literals import (
    IRI,
    Annotation,
    DataIntersectionOf,
    DataOneOf,
    DataType,
    LangLiteral,
    TypedLiteral,
)

# -- Annotation exclusion --


def test_annotations_excluded_from_canonical_json():
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
    assert canonical_json(a1) == canonical_json(a2)


def test_axiom_hash_stable_across_annotations():
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax2 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
        annotations=(Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note")),),
    )
    assert axiom_hash(ax1) == axiom_hash(ax2)


def test_axiom_hash_different_for_different_content():
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax2 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Cat")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    assert axiom_hash(ax1) != axiom_hash(ax2)


# -- Set-semantic sorting: axiom-level --


def test_equivalent_classes_order_irrelevant():
    a, b, c = IRI("ex:A"), IRI("ex:B"), IRI("ex:C")
    ax1 = EquivalentClasses(expressions=(NamedClass(iri=a), NamedClass(iri=b), NamedClass(iri=c)))
    ax2 = EquivalentClasses(expressions=(NamedClass(iri=c), NamedClass(iri=a), NamedClass(iri=b)))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_disjoint_classes_order_irrelevant():
    ax1 = DisjointClasses(expressions=(NamedClass(iri=IRI("ex:A")), NamedClass(iri=IRI("ex:B"))))
    ax2 = DisjointClasses(expressions=(NamedClass(iri=IRI("ex:B")), NamedClass(iri=IRI("ex:A"))))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_equivalent_object_properties_order_irrelevant():
    ax1 = EquivalentObjectProperties(properties=(IRI("ex:p"), IRI("ex:q"), IRI("ex:r")))
    ax2 = EquivalentObjectProperties(properties=(IRI("ex:r"), IRI("ex:p"), IRI("ex:q")))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_equivalent_data_properties_order_irrelevant():
    ax1 = EquivalentDataProperties(properties=(IRI("ex:dp1"), IRI("ex:dp2")))
    ax2 = EquivalentDataProperties(properties=(IRI("ex:dp2"), IRI("ex:dp1")))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_same_individual_order_irrelevant():
    ax1 = SameIndividual(individuals=(IRI("ex:a"), IRI("ex:b")))
    ax2 = SameIndividual(individuals=(IRI("ex:b"), IRI("ex:a")))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_different_individuals_order_irrelevant():
    ax1 = DifferentIndividuals(individuals=(IRI("ex:a"), IRI("ex:b"), IRI("ex:c")))
    ax2 = DifferentIndividuals(individuals=(IRI("ex:c"), IRI("ex:a"), IRI("ex:b")))
    assert canonical_json(ax1) == canonical_json(ax2)


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
    assert canonical_json(ax1) == canonical_json(ax2)


# -- Set-semantic sorting: expression-level (recursive) --


def test_intersection_operands_sorted():
    a = NamedClass(iri=IRI("ex:A"))
    b = NamedClass(iri=IRI("ex:B"))
    expr1 = ObjectIntersectionOf(operands=(a, b))
    expr2 = ObjectIntersectionOf(operands=(b, a))
    ax1 = SubClassOf(sub_class=NamedClass(iri=IRI("ex:X")), super_class=expr1)
    ax2 = SubClassOf(sub_class=NamedClass(iri=IRI("ex:X")), super_class=expr2)
    assert canonical_json(ax1) == canonical_json(ax2)


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
    assert canonical_json(ax1) == canonical_json(ax2)


# -- Order-sensitive fields preserved --


def test_subclassof_order_preserved():
    a = NamedClass(iri=IRI("ex:A"))
    b = NamedClass(iri=IRI("ex:B"))
    ax1 = SubClassOf(sub_class=a, super_class=b)
    ax2 = SubClassOf(sub_class=b, super_class=a)
    assert canonical_json(ax1) != canonical_json(ax2)


# -- DataRange normalization --


def test_data_intersection_operand_order_irrelevant():
    ax1 = DataPropertyRange(
        property=IRI("ex:hasAge"),
        range=DataIntersectionOf(operands=(DataType.INTEGER, DataType.DECIMAL)),
    )
    ax2 = DataPropertyRange(
        property=IRI("ex:hasAge"),
        range=DataIntersectionOf(operands=(DataType.DECIMAL, DataType.INTEGER)),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


def test_datatype_definition_with_data_intersection():
    ax1 = DatatypeDefinition(
        datatype=IRI("ex:PosInt"),
        data_range=DataIntersectionOf(operands=(DataType.INTEGER, DataType.NON_NEGATIVE_INTEGER)),
    )
    ax2 = DatatypeDefinition(
        datatype=IRI("ex:PosInt"),
        data_range=DataIntersectionOf(operands=(DataType.NON_NEGATIVE_INTEGER, DataType.INTEGER)),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


def test_data_intersection_with_data_one_of_operand():
    one = DataOneOf(value=TypedLiteral(value="1", datatype=DataType.INTEGER))
    ax1 = DataPropertyRange(
        property=IRI("ex:p"),
        range=DataIntersectionOf(operands=(DataType.INTEGER, one)),
    )
    ax2 = DataPropertyRange(
        property=IRI("ex:p"),
        range=DataIntersectionOf(operands=(one, DataType.INTEGER)),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


def test_data_some_values_from_with_data_intersection():
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:A")),
        super_class=DataSomeValuesFrom(
            property=IRI("ex:p"),
            range=DataIntersectionOf(operands=(DataType.STRING, DataType.TOKEN)),
        ),
    )
    ax2 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:A")),
        super_class=DataSomeValuesFrom(
            property=IRI("ex:p"),
            range=DataIntersectionOf(operands=(DataType.TOKEN, DataType.STRING)),
        ),
    )
    assert canonical_json(ax1) == canonical_json(ax2)
