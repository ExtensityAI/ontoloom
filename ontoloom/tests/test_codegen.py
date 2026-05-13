from ontoloom.patterns.codegen import generate_body


def test_gen_patterns_produces_python_source():
    source = generate_body()
    assert "class SubClassOfPattern" in source
    assert "Pattern = Annotated[" in source
    assert "tagged_union_meta(_get_pattern_tag)" in source


def test_gen_patterns_is_deterministic():
    assert generate_body() == generate_body()


def test_gen_patterns_iri_fields_become_slot():
    source = generate_body()
    # AnnotationAssertion.property (IRI) → Slot
    assert "property: Slot" in source


def test_gen_patterns_class_expression_becomes_exprslot():
    source = generate_body()
    # SubClassOf.sub_class (ClassExpression) → ExprSlot
    assert "sub_class: ExprSlot" in source
    assert "super_class: ExprSlot" in source


def test_gen_patterns_unordered_tuple_gets_sibling_match_enum():
    source = generate_body()
    # Unordered tuple field -> bare tuple + sibling `<field>_match: TupleMatch`
    assert "equivalent_classes: tuple[ExprSlot, ...]" in source
    assert "equivalent_classes_match: TupleMatch = TupleMatch.EXACT" in source
    assert "object_properties: tuple[Slot, ...]" in source
    assert "object_properties_match: TupleMatch = TupleMatch.EXACT" in source


def test_gen_patterns_ordered_tuple_has_no_sibling_match():
    source = generate_body()
    # SubObjectPropertyOfChain.chain is ordered -> bare tuple, no sibling
    assert "chain: tuple[Slot, ...]" in source
    assert "chain_match" not in source


def test_gen_patterns_data_range_gets_slot_option():
    source = generate_body()
    assert "DataRange | Slot" in source


def test_gen_patterns_exprslot_alias_defined():
    source = generate_body()
    assert "ExprSlot = Slot |" in source


def test_new_axiom_type_works_without_module_edits():
    """Adding a new axiom type with markers -> canonical and extract pick it up
    purely from the field metadata, no edits to canonical.py or extract.py needed."""
    from typing import Annotated, Literal

    from ontoloom.canonical import canonical_json
    from ontoloom.entity_walker import iter_axiom_entities
    from ontoloom.owl.axioms import BaseAxiom
    from ontoloom.owl.iri import IRI
    from ontoloom.owl.markers import EntityType, Position, Unordered
    from pydantic import Field

    class _TestAxiom(BaseAxiom):
        type: Literal["_TestAxiom"] = "_TestAxiom"
        members: Annotated[
            tuple[IRI, ...],
            Unordered(),
            EntityType.CLASS,
            Position.MEMBER,
            Field(min_length=2),
        ]

    a = _TestAxiom(members=(IRI("ex:Dog"), IRI("ex:Cat")))
    b = _TestAxiom(members=(IRI("ex:Cat"), IRI("ex:Dog")))
    assert canonical_json(a) == canonical_json(b)  # Unordered marker → sorted

    entities = set(iter_axiom_entities(a))
    assert (IRI("ex:Dog"), EntityType.CLASS, Position.MEMBER) in entities
    assert (IRI("ex:Cat"), EntityType.CLASS, Position.MEMBER) in entities


# -- P-03-10: Cross-process determinism --


def test_gen_patterns_cross_process_deterministic():
    import subprocess
    import sys

    script = "from ontoloom.patterns.codegen import generate_body; print(generate_body(), end='')"

    def run(seed: int):
        return subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONHASHSEED": str(seed)},
            check=True,
        ).stdout

    assert run(0) == run(1)


# -- P-03-12: Structural codegen tests --


def test_gen_patterns_fields_match_axiom_fields():
    from typing import get_args

    from ontoloom.owl.axioms import Axiom
    from ontoloom.patterns.types import AxiomPattern

    skip = frozenset(("type", "annotations"))
    axiom_classes = {cls.__name__: cls for cls in get_args(get_args(Axiom)[0])}
    pattern_classes = {cls.__name__: cls for cls in get_args(AxiomPattern)}

    for pattern_name, pattern_cls in pattern_classes.items():
        axiom_name = pattern_name.removesuffix("Pattern")
        axiom_cls = axiom_classes.get(axiom_name)
        if axiom_cls is None:
            continue

        axiom_fields = set(axiom_cls.model_fields) - skip
        pattern_fields = set(pattern_cls.model_fields) - skip
        assert pattern_fields == axiom_fields, (
            f"{pattern_name}: expected fields {axiom_fields}, got {pattern_fields}"
        )


def test_exprslot_and_axiomslot_exact_membership():
    from typing import get_args

    from ontoloom.patterns.slot import Slot
    from ontoloom.patterns.types import AxiomPattern, ExpressionPattern, ExprSlot

    expr_types = set(get_args(ExpressionPattern))
    exprslot_types = set(get_args(ExprSlot))
    assert Slot in exprslot_types
    assert exprslot_types == {Slot} | expr_types

    # AxiomPattern is a plain union of all axiom pattern classes
    axiom_types = set(get_args(AxiomPattern))
    assert len(axiom_types) > 0


def test_expression_container_types_reflective_derivation():
    """_EXPRESSION_CONTAINER_TYPES must match the axiom types that actually carry ClassExpression fields."""
    from ontoloom.patterns.store import _EXPRESSION_CONTAINER_TYPES

    expected = frozenset(
        {
            "ClassAssertion",
            "DataPropertyDomain",
            "DisjointClasses",
            "EquivalentClasses",
            "HasKey",
            "ObjectPropertyDomain",
            "ObjectPropertyRange",
            "SubClassOf",
        }
    )
    assert expected == _EXPRESSION_CONTAINER_TYPES


def test_gen_patterns_field_type_transformations():
    """Key field-type transformations verified at runtime via model_fields annotations."""
    from typing import Annotated, get_args, get_origin

    from ontoloom.patterns import types as gen
    from ontoloom.patterns.slot import Slot

    def _strip_annotated(t):
        return get_args(t)[0] if get_origin(t) is Annotated else t

    # `Slot` is `Annotated[Union[...], Discriminator, Field]`; the outer Annotated
    # gets stripped when Slot is a direct field annotation but preserved when it's
    # a union member, so normalize before comparing.
    slot_inner = _strip_annotated(Slot)

    # IRI field → Slot
    ann = gen.AnnotationAssertionPattern.model_fields["property"].annotation
    assert _strip_annotated(ann) == slot_inner, f"expected Slot for .property, got {ann}"

    # ClassExpression field → ExprSlot (a union containing Slot)
    ann = gen.SubClassOfPattern.model_fields["sub_class"].annotation
    args = [_strip_annotated(a) for a in get_args(ann)]
    assert args, f"expected union for .sub_class, got {ann}"
    assert slot_inner in args, f"Slot missing from ExprSlot union: {ann}"

    # DataRange field → DataRange | Slot (union containing Slot)
    ann = gen.DataPropertyRangePattern.model_fields["range"].annotation
    args = [_strip_annotated(a) for a in get_args(ann)]
    assert args, f"expected union for .range, got {ann}"
    assert slot_inner in args, f"Slot missing from DataRange|Slot union: {ann}"

    # Ordered tuple of IRI → tuple[Slot, ...] (no sibling _match)
    ann = gen.SubObjectPropertyOfChainPattern.model_fields["chain"].annotation
    inner = _strip_annotated(get_args(ann)[0])
    assert inner == slot_inner, f"expected tuple[Slot, ...] for .chain, got {ann}"
    assert "chain_match" not in gen.SubObjectPropertyOfChainPattern.model_fields

    # Unordered tuple of IRI → tuple[Slot, ...] + sibling `<field>_match`
    ann = gen.EquivalentObjectPropertiesPattern.model_fields["object_properties"].annotation
    inner = _strip_annotated(get_args(ann)[0])
    assert inner == slot_inner, f"expected tuple[Slot, ...] for object_properties, got {ann}"
    assert "object_properties_match" in gen.EquivalentObjectPropertiesPattern.model_fields
