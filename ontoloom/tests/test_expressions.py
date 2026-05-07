from pydantic import TypeAdapter

from ontoloom.canonical import canonical_json
from ontoloom.entity_walker import iter_axiom_entities
from ontoloom.owl.axioms import AnnotationAssertion, SubClassOf
from ontoloom.owl.expressions import ClassExpression, ObjectHasSelf, is_class_expression
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType, Position


def test_iri_instance_returns_true():
    iri = IRI(":Dog")
    assert is_class_expression(iri)


def test_base_class_expression_instance_returns_true():
    expr = ObjectHasSelf(self_property=IRI(":likes"))
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


# -- Bare IRI as ClassExpression (Task 5) --


def test_bare_iri_validates_as_class_expression():
    """A bare IRI string must validate via the ClassExpression union."""
    adapter = TypeAdapter(ClassExpression)
    result = adapter.validate_python(":Dog")
    assert isinstance(result, str)
    assert result == ":Dog"


def test_bare_iri_in_subclassof_extracts_class_entities():
    """SubClassOf built from bare IRIs must yield CLASS-typed entities at SUB/SUPER positions."""
    ax = SubClassOf(sub_class=IRI(":Dog"), super_class=IRI(":Animal"))
    entities = [(str(iri), kind, pos) for iri, kind, pos in iter_axiom_entities(ax)]
    assert (":Dog", EntityType.CLASS, Position.SUB_CLASS) in entities
    assert (":Animal", EntityType.CLASS, Position.SUPER_CLASS) in entities


def test_canonical_renders_bare_iri_class_expressions_as_strings():
    """Bare-IRI class expressions serialize as plain strings, not wrapped objects."""
    ax = SubClassOf(sub_class=IRI(":Dog"), super_class=IRI(":Animal"))
    rendered = canonical_json(ax)
    assert '"sub_class":":Dog"' in rendered
    assert '"super_class":":Animal"' in rendered
