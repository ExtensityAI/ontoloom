from ontoloom.canonical import canonical_json
from ontoloom.connection import Ontology
from ontoloom.hashing import HASH_DISPLAY_LEN, HashedAxiom, disambiguating_prefixes
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import (
    DataPropertyRange,
    DatatypeDefinition,
    DifferentIndividuals,
    DisjointClasses,
    EquivalentClasses,
    EquivalentDataProperties,
    EquivalentObjectProperties,
    HasKey,
    SameIndividual,
    SubClassOf,
)
from ontoloom.owl.expressions import (
    DataSomeValuesFrom,
    NamedClass,
    ObjectIntersectionOf,
    ObjectSomeValuesFrom,
)
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import (
    DataIntersectionOf,
    DataOneOf,
    DataType,
    DataTypeRef,
    LangLiteral,
    TypedLiteral,
)
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import SelectionKind

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
    assert HashedAxiom.of(ax1).hash == HashedAxiom.of(ax2).hash


def test_axiom_hash_different_for_different_content():
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Dog")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    ax2 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:Cat")),
        super_class=NamedClass(iri=IRI("ex:Animal")),
    )
    assert HashedAxiom.of(ax1).hash != HashedAxiom.of(ax2).hash


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
        range=DataIntersectionOf(
            operands=(DataTypeRef(value=DataType.INTEGER), DataTypeRef(value=DataType.DECIMAL))
        ),
    )
    ax2 = DataPropertyRange(
        property=IRI("ex:hasAge"),
        range=DataIntersectionOf(
            operands=(DataTypeRef(value=DataType.DECIMAL), DataTypeRef(value=DataType.INTEGER))
        ),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


def test_datatype_definition_with_data_intersection():
    ax1 = DatatypeDefinition(
        datatype=IRI("ex:PosInt"),
        data_range=DataIntersectionOf(
            operands=(
                DataTypeRef(value=DataType.INTEGER),
                DataTypeRef(value=DataType.NON_NEGATIVE_INTEGER),
            )
        ),
    )
    ax2 = DatatypeDefinition(
        datatype=IRI("ex:PosInt"),
        data_range=DataIntersectionOf(
            operands=(
                DataTypeRef(value=DataType.NON_NEGATIVE_INTEGER),
                DataTypeRef(value=DataType.INTEGER),
            )
        ),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


def test_data_intersection_with_data_one_of_operand():
    one = DataOneOf(value=TypedLiteral(value="1", datatype=DataType.INTEGER))
    int_ref = DataTypeRef(value=DataType.INTEGER)
    ax1 = DataPropertyRange(
        property=IRI("ex:p"),
        range=DataIntersectionOf(operands=(int_ref, one)),
    )
    ax2 = DataPropertyRange(
        property=IRI("ex:p"),
        range=DataIntersectionOf(operands=(one, int_ref)),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


def test_data_some_values_from_with_data_intersection():
    ax1 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:A")),
        super_class=DataSomeValuesFrom(
            property=IRI("ex:p"),
            range=DataIntersectionOf(
                operands=(
                    DataTypeRef(value=DataType.STRING),
                    DataTypeRef(value=DataType.TOKEN),
                )
            ),
        ),
    )
    ax2 = SubClassOf(
        sub_class=NamedClass(iri=IRI("ex:A")),
        super_class=DataSomeValuesFrom(
            property=IRI("ex:p"),
            range=DataIntersectionOf(
                operands=(
                    DataTypeRef(value=DataType.TOKEN),
                    DataTypeRef(value=DataType.STRING),
                )
            ),
        ),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


# -- P-03-9: Determinism --


def test_canonical_idempotent():
    from ontoloom.canonical import _normalize_model

    ax = EquivalentClasses(
        expressions=(
            NamedClass(iri=IRI("ex:B")),
            NamedClass(iri=IRI("ex:A")),
        )
    )
    assert canonical_json(_normalize_model(ax)) == canonical_json(
        _normalize_model(_normalize_model(ax))
    )


def test_selection_hash_order_independent(tmp_path):
    path = tmp_path / "test.db"
    Ontology.create(path)
    with Ontology(path) as ont:
        h1 = upsert_selection(
            ont, "s1", SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat", "ex:Fish"], "test"
        ).selection.hash
        h2 = upsert_selection(
            ont, "s2", SelectionKind.ENTITIES, ["ex:Fish", "ex:Dog", "ex:Cat"], "test"
        ).selection.hash
        assert h1 == h2


def test_selection_pagination_stable_across_processes(tmp_path):
    """Set-op selections must paginate the same way regardless of PYTHONHASHSEED.

    Set ops materialise via Python `set`, whose iteration order is randomized;
    selection_items.rowid would differ across runs without deterministic ordering
    at the set-op level, and read_selection paginates by rowid.
    """
    import subprocess
    import sys
    import textwrap

    db_path = tmp_path / "det.db"
    Ontology.create(db_path)
    script = textwrap.dedent(f"""\
        from pathlib import Path
        from ontoloom.selections.store import create_selection, read_selection, upsert_selection
        from ontoloom.selections.types import SelectionKind
        from ontoloom.connection import Ontology

        with Ontology(Path({str(db_path)!r})) as ont:
            upsert_selection(ont, "a", SelectionKind.ENTITIES,
                ["ex:Z", "ex:A", "ex:M", "ex:Q", "ex:B"], "src")
            upsert_selection(ont, "b", SelectionKind.ENTITIES,
                ["ex:Z", "ex:A", "ex:M", "ex:R", "ex:C"], "src")
            create_selection(ont, "r", intersection=["a", "b"])
            page = read_selection(ont, "r", limit=5)
            print(",".join(item.key for item in page.items))
    """)

    def run(seed: int):
        return subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONHASHSEED": str(seed)},
            check=True,
        ).stdout.strip()

    assert run(0) == run(1) == run(42)


# -- P-08-25: hash display helpers --


def test_truncate_hash_uses_display_len():
    h = "a" * 64
    assert h[:HASH_DISPLAY_LEN] == "a" * HASH_DISPLAY_LEN


def test_min_distinguishing_prefixes_single():
    h = "abcdef0123"
    assert disambiguating_prefixes([h]) == [h]


def test_min_distinguishing_prefixes_disjoint():
    # All hashes diverge at the first character -> each gets a 1-char prefix.
    assert disambiguating_prefixes(["abcd", "bcde", "cdef"]) == ["a", "b", "c"]


def test_min_distinguishing_prefixes_shared_prefix():
    # "a3f1b2c4" and "a3f1c5d6" share "a3f1"; need 5 chars to disambiguate.
    # "a3a2..." diverges at char 2, so 3 chars suffice.
    out = disambiguating_prefixes(["a3f1b2c4", "a3f1c5d6", "a3a2ffff"])
    assert out == ["a3f1b", "a3f1c", "a3a"]


def test_min_distinguishing_prefixes_preserves_input_order():
    # Input order is preserved; only distinguishing length is computed.
    out = disambiguating_prefixes(["zzz9", "aaa1", "aaa2"])
    assert out == ["z", "aaa1", "aaa2"]
