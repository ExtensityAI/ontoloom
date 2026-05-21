from ontoloom.axioms.entity_walker import iter_axiom_entities
from ontoloom.canonical import canonical_json
from ontoloom.owl.axioms import SubClassOf
from ontoloom.owl.expressions import ClassExpression
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType, Position
from pydantic import TypeAdapter

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
