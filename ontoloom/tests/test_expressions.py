from ontoloom.owl.axioms import AnnotationAssertion
from ontoloom.owl.expressions import ObjectHasSelf, is_class_expression
from ontoloom.owl.iri import IRI


def test_iri_instance_returns_true():
    iri = IRI(":Dog")
    assert is_class_expression(iri)


def test_base_class_expression_instance_returns_true():
    expr = ObjectHasSelf(property=IRI(":likes"))
    assert is_class_expression(expr)


def test_plain_int_returns_false():
    assert not is_class_expression(42)


def test_plain_dict_returns_false():
    assert not is_class_expression({"key": "value"})


def test_plain_none_returns_false():
    assert not is_class_expression(None)


def test_plain_str_returns_false():
    assert not is_class_expression("plain string")


def test_non_class_expression_owl_model_returns_false():
    annotation_axiom = AnnotationAssertion(
        property=IRI(":label"),
        subject=IRI(":Dog"),
        value=IRI(":LabelValue"),
    )
    assert not is_class_expression(annotation_axiom)
