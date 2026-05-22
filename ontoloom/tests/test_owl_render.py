"""Direct tests for owl._render.format_owl_struct.

Targets the renderer's format permutations rather than relying on canonical/
extract integration coverage. Synthetic Pydantic models exercise the
permutation matrix; real OWL types confirm the renderer matches what the
audit and downstream consumers expect.
"""

from ontoloom.owl._render import format_owl_struct
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import (
    Declaration,
    EquivalentClasses,
    HasKey,
    SameIndividual,
    SubClassOf,
)
from ontoloom.owl.expressions import ObjectSomeValuesFrom
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from pydantic import BaseModel

# -- Synthetic permutation coverage --


class _Scalars(BaseModel):
    a: str
    b: int


class _OnlyTuple(BaseModel):
    items: tuple[str, ...]


class _MultiWithTuple(BaseModel):
    head: str
    rest: tuple[str, ...]


class _WithSkipFields(BaseModel):
    real: str
    annotations: tuple[str, ...] = ()
    negated: bool = False


def test_scalars_render_positionally():
    assert format_owl_struct(_Scalars(a="x", b=7)) == "_Scalars(x, 7)"


def test_only_tuple_field_flattens_args():
    assert format_owl_struct(_OnlyTuple(items=("a", "b", "c"))) == "_OnlyTuple(a, b, c)"


def test_multi_field_tuple_uses_brackets():
    assert (
        format_owl_struct(_MultiWithTuple(head="X", rest=("a", "b")))
        == "_MultiWithTuple(X, [a, b])"
    )


def test_empty_tuple_in_multi_field_yields_empty_brackets():
    assert format_owl_struct(_MultiWithTuple(head="X", rest=())) == "_MultiWithTuple(X, [])"


def test_skip_fields_excluded_from_render():
    rendered = format_owl_struct(_WithSkipFields(real="v", annotations=("a",), negated=True))
    assert rendered == "_WithSkipFields(v)"


# -- Real OWL types --


def test_declaration_renders_enum_value():
    obj = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))
    assert format_owl_struct(obj) == "Declaration(Class, ex:Dog)"


def test_subclassof_renders_iris_positionally():
    obj = SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    assert format_owl_struct(obj) == "SubClassOf(ex:Dog, ex:Animal)"


def test_equivalent_classes_uses_only_tuple_flat_form():
    obj = EquivalentClasses(equivalent_classes=(IRI("ex:Dog"), IRI("ex:Hund")))
    assert format_owl_struct(obj) == "EquivalentClasses(ex:Dog, ex:Hund)"


def test_same_individual_uses_only_tuple_flat_form():
    obj = SameIndividual(same_individuals=(IRI("ex:fido"), IRI("ex:rover")))
    assert format_owl_struct(obj) == "SameIndividual(ex:fido, ex:rover)"


def test_nested_owl_struct_renders_recursively():
    inner = ObjectSomeValuesFrom(property=IRI("ex:hasPart"), filler=IRI("ex:Heart"))
    outer = SubClassOf(sub_class=IRI("ex:Animal"), super_class=inner)
    assert (
        format_owl_struct(outer)
        == "SubClassOf(ex:Animal, ObjectSomeValuesFrom(ex:hasPart, ex:Heart))"
    )


def test_has_key_multi_field_tuples_use_brackets():
    obj = HasKey(
        class_expression=IRI("ex:Person"),
        has_key_object_properties=(IRI("ex:hasSSN"),),
        has_key_data_properties=(IRI("ex:fingerprint"),),
    )
    assert format_owl_struct(obj) == "HasKey(ex:Person, [ex:hasSSN], [ex:fingerprint])"


def test_axiom_annotations_excluded_from_render():
    obj = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="x")),),
    )
    assert format_owl_struct(obj) == "SubClassOf(ex:Dog, ex:Animal)"
