from ontoloom.owl.axioms import EquivalentClasses
from ontoloom.owl.iri import IRI
from ontoloom.patterns.match import match_pattern
from ontoloom.patterns.slot import Slot
from ontoloom.patterns.types import EquivalentClassesPattern


def test_equivalent_classes_pattern_order_insensitive():
    axiom = EquivalentClasses(equivalent_classes=(IRI("ex:Cat"), IRI("ex:Dog")))
    pattern = EquivalentClassesPattern(
        equivalent_classes=(
            Slot("ex:Dog"),
            Slot("ex:Cat"),
        ),
    )
    bindings = match_pattern(pattern, axiom)
    assert bindings == [{}]


def test_equivalent_classes_pattern_length_mismatch():
    """Unordered tuple match still requires equal lengths."""
    axiom = EquivalentClasses(
        equivalent_classes=(
            IRI("ex:Cat"),
            IRI("ex:Dog"),
            IRI("ex:Bird"),
        )
    )
    pattern = EquivalentClassesPattern(
        equivalent_classes=(
            Slot("ex:Dog"),
            Slot("ex:Cat"),
        ),
    )
    assert match_pattern(pattern, axiom) == []


def test_chain_pattern_order_sensitive():
    """SubObjectPropertyOfChain.chain is ordered -> match_pattern must respect order."""
    from ontoloom.owl.axioms import SubObjectPropertyOfChain
    from ontoloom.patterns.types import SubObjectPropertyOfChainPattern

    axiom = SubObjectPropertyOfChain(
        chain=(IRI("ex:hasParent"), IRI("ex:hasBrother")),
        super_property=IRI("ex:hasUncle"),
    )
    swapped = SubObjectPropertyOfChainPattern(
        chain=(Slot("ex:hasBrother"), Slot("ex:hasParent")),
        super_property=Slot("ex:hasUncle"),
    )
    assert match_pattern(swapped, axiom) == []
