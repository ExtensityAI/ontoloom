from ontoloom.ontology.models.axioms import EquivalentClasses
from ontoloom.ontology.models.expressions import NamedClass
from ontoloom.ontology.models.literals import IRI
from ontoloom.ontology.patterns import EquivalentClassesPattern, NamedClassPattern
from ontoloom.ontology.patterns.match import match_pattern


def test_equivalent_classes_pattern_order_insensitive():
    axiom = EquivalentClasses(
        expressions=(NamedClass(iri=IRI("ex:Cat")), NamedClass(iri=IRI("ex:Dog")))
    )
    pattern = EquivalentClassesPattern(
        expressions=(
            NamedClassPattern(iri="ex:Dog"),
            NamedClassPattern(iri="ex:Cat"),
        ),
    )
    bindings = match_pattern(pattern, axiom)
    assert bindings == [{}]


def test_equivalent_classes_pattern_length_mismatch():
    """Unordered tuple match still requires equal lengths."""
    axiom = EquivalentClasses(
        expressions=(
            NamedClass(iri=IRI("ex:Cat")),
            NamedClass(iri=IRI("ex:Dog")),
            NamedClass(iri=IRI("ex:Bird")),
        )
    )
    pattern = EquivalentClassesPattern(
        expressions=(
            NamedClassPattern(iri="ex:Dog"),
            NamedClassPattern(iri="ex:Cat"),
        ),
    )
    assert match_pattern(pattern, axiom) == []


def test_chain_pattern_order_sensitive():
    """SubObjectPropertyOfChain.chain is ordered — match_pattern must respect order."""
    from ontoloom.ontology.models.axioms import SubObjectPropertyOfChain
    from ontoloom.ontology.patterns import SubObjectPropertyOfChainPattern

    axiom = SubObjectPropertyOfChain(
        chain=(IRI("ex:hasParent"), IRI("ex:hasBrother")),
        super_property=IRI("ex:hasUncle"),
    )
    swapped = SubObjectPropertyOfChainPattern(
        chain=("ex:hasBrother", "ex:hasParent"),
        super_property="ex:hasUncle",
    )
    assert match_pattern(swapped, axiom) == []
