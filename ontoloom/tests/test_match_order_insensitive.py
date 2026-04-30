from ontoloom.ontology.models.axioms import EquivalentClasses
from ontoloom.ontology.models.expressions import NamedClass
from ontoloom.ontology.models.literals import IRI
from ontoloom.ontology.patterns import EquivalentClassesPattern, NamedClassPattern
from ontoloom.ontology.patterns.match import _match_pattern
from ontoloom.ontology.patterns.slot import Slot


def test_equivalent_classes_pattern_order_insensitive():
    axiom = EquivalentClasses(
        expressions=(NamedClass(iri=IRI("ex:Cat")), NamedClass(iri=IRI("ex:Dog")))
    )
    pattern = EquivalentClassesPattern(
        expressions=(
            NamedClassPattern(iri=Slot("ex:Dog")),
            NamedClassPattern(iri=Slot("ex:Cat")),
        ),
    )
    bindings = _match_pattern(pattern, axiom)
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
            NamedClassPattern(iri=Slot("ex:Dog")),
            NamedClassPattern(iri=Slot("ex:Cat")),
        ),
    )
    assert _match_pattern(pattern, axiom) == []


def test_chain_pattern_order_sensitive():
    """SubObjectPropertyOfChain.chain is ordered — match_pattern must respect order."""
    from ontoloom.ontology.models.axioms import SubObjectPropertyOfChain
    from ontoloom.ontology.patterns import SubObjectPropertyOfChainPattern

    axiom = SubObjectPropertyOfChain(
        chain=(IRI("ex:hasParent"), IRI("ex:hasBrother")),
        super_property=IRI("ex:hasUncle"),
    )
    swapped = SubObjectPropertyOfChainPattern(
        chain=(Slot("ex:hasBrother"), Slot("ex:hasParent")),
        super_property=Slot("ex:hasUncle"),
    )
    assert _match_pattern(swapped, axiom) == []
