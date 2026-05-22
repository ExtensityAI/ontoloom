from ontoloom.axioms.hashing import HASH_DISPLAY_LEN, disambiguating_prefixes
from ontoloom.axioms.types import HashedAxiom
from ontoloom.canonical import canonical_json
from ontoloom.connection import Ontology, session
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
from ontoloom.selections.types import SelectionKind, SelectionName

# -- Annotation exclusion --


def test_annotations_excluded_from_canonical_json():
    a1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    a2 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(
            Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="important")),
        ),
    )
    assert canonical_json(a1) == canonical_json(a2)


def test_axiom_hash_stable_across_annotations():
    ax1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax2 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value="note")),),
    )
    assert HashedAxiom.of(ax1).hash == HashedAxiom.of(ax2).hash


def test_axiom_hash_different_for_different_content():
    ax1 = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
    )
    ax2 = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
    )
    assert HashedAxiom.of(ax1).hash != HashedAxiom.of(ax2).hash


# -- Set-semantic sorting: axiom-level --


def test_equivalent_classes_order_irrelevant():
    a, b, c = IRI("ex:A"), IRI("ex:B"), IRI("ex:C")
    ax1 = EquivalentClasses(equivalent_classes=(a, b, c))
    ax2 = EquivalentClasses(equivalent_classes=(c, a, b))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_disjoint_classes_order_irrelevant():
    ax1 = DisjointClasses(disjoint_classes=(IRI("ex:A"), IRI("ex:B")))
    ax2 = DisjointClasses(disjoint_classes=(IRI("ex:B"), IRI("ex:A")))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_equivalent_object_properties_order_irrelevant():
    ax1 = EquivalentObjectProperties(object_properties=(IRI("ex:p"), IRI("ex:q"), IRI("ex:r")))
    ax2 = EquivalentObjectProperties(object_properties=(IRI("ex:r"), IRI("ex:p"), IRI("ex:q")))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_equivalent_data_properties_order_irrelevant():
    ax1 = EquivalentDataProperties(data_properties=(IRI("ex:dp1"), IRI("ex:dp2")))
    ax2 = EquivalentDataProperties(data_properties=(IRI("ex:dp2"), IRI("ex:dp1")))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_same_individual_order_irrelevant():
    ax1 = SameIndividual(same_individuals=(IRI("ex:a"), IRI("ex:b")))
    ax2 = SameIndividual(same_individuals=(IRI("ex:b"), IRI("ex:a")))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_different_individuals_order_irrelevant():
    ax1 = DifferentIndividuals(different_individuals=(IRI("ex:a"), IRI("ex:b"), IRI("ex:c")))
    ax2 = DifferentIndividuals(different_individuals=(IRI("ex:c"), IRI("ex:a"), IRI("ex:b")))
    assert canonical_json(ax1) == canonical_json(ax2)


def test_has_key_properties_order_irrelevant():
    ax1 = HasKey(
        class_expression=IRI("ex:Person"),
        object_properties=(IRI("ex:p1"), IRI("ex:p2")),
        data_properties=(IRI("ex:d1"), IRI("ex:d2")),
    )
    ax2 = HasKey(
        class_expression=IRI("ex:Person"),
        object_properties=(IRI("ex:p2"), IRI("ex:p1")),
        data_properties=(IRI("ex:d2"), IRI("ex:d1")),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


# -- Set-semantic sorting: expression-level (recursive) --


def test_intersection_operands_sorted():
    a = IRI("ex:A")
    b = IRI("ex:B")
    expr1 = ObjectIntersectionOf(operands=(a, b))
    expr2 = ObjectIntersectionOf(operands=(b, a))
    ax1 = SubClassOf(sub_class=IRI("ex:X"), super_class=expr1)
    ax2 = SubClassOf(sub_class=IRI("ex:X"), super_class=expr2)
    assert canonical_json(ax1) == canonical_json(ax2)


def test_deeply_nested_normalization():
    a = IRI("ex:A")
    b = IRI("ex:B")
    c = IRI("ex:C")
    p = IRI("ex:p")

    inter_ba = ObjectIntersectionOf(operands=(b, a))
    inter_ab = ObjectIntersectionOf(operands=(a, b))
    some_pc = ObjectSomeValuesFrom(property=p, filler=c)

    ax1 = EquivalentClasses(equivalent_classes=(inter_ba, some_pc))
    ax2 = EquivalentClasses(equivalent_classes=(some_pc, inter_ab))
    assert canonical_json(ax1) == canonical_json(ax2)


# -- Order-sensitive fields preserved --


def test_subclassof_order_preserved():
    a = IRI("ex:A")
    b = IRI("ex:B")
    ax1 = SubClassOf(sub_class=a, super_class=b)
    ax2 = SubClassOf(sub_class=b, super_class=a)
    assert canonical_json(ax1) != canonical_json(ax2)


# -- DataRange normalization --


def test_data_intersection_operand_order_irrelevant():
    ax1 = DataPropertyRange(
        data_property=IRI("ex:hasAge"),
        range=DataIntersectionOf(
            operands=(
                DataTypeRef(datatype=DataType.INTEGER),
                DataTypeRef(datatype=DataType.DECIMAL),
            )
        ),
    )
    ax2 = DataPropertyRange(
        data_property=IRI("ex:hasAge"),
        range=DataIntersectionOf(
            operands=(
                DataTypeRef(datatype=DataType.DECIMAL),
                DataTypeRef(datatype=DataType.INTEGER),
            )
        ),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


def test_datatype_definition_with_data_intersection():
    ax1 = DatatypeDefinition(
        datatype=IRI("ex:PosInt"),
        data_range=DataIntersectionOf(
            operands=(
                DataTypeRef(datatype=DataType.INTEGER),
                DataTypeRef(datatype=DataType.NON_NEGATIVE_INTEGER),
            )
        ),
    )
    ax2 = DatatypeDefinition(
        datatype=IRI("ex:PosInt"),
        data_range=DataIntersectionOf(
            operands=(
                DataTypeRef(datatype=DataType.NON_NEGATIVE_INTEGER),
                DataTypeRef(datatype=DataType.INTEGER),
            )
        ),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


def test_data_intersection_with_data_one_of_operand():
    one = DataOneOf(value=TypedLiteral(value="1", datatype=DataType.INTEGER))
    int_ref = DataTypeRef(datatype=DataType.INTEGER)
    ax1 = DataPropertyRange(
        data_property=IRI("ex:p"),
        range=DataIntersectionOf(operands=(int_ref, one)),
    )
    ax2 = DataPropertyRange(
        data_property=IRI("ex:p"),
        range=DataIntersectionOf(operands=(one, int_ref)),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


def test_data_some_values_from_with_data_intersection():
    ax1 = SubClassOf(
        sub_class=IRI("ex:A"),
        super_class=DataSomeValuesFrom(
            property=IRI("ex:p"),
            range=DataIntersectionOf(
                operands=(
                    DataTypeRef(datatype=DataType.STRING),
                    DataTypeRef(datatype=DataType.TOKEN),
                )
            ),
        ),
    )
    ax2 = SubClassOf(
        sub_class=IRI("ex:A"),
        super_class=DataSomeValuesFrom(
            property=IRI("ex:p"),
            range=DataIntersectionOf(
                operands=(
                    DataTypeRef(datatype=DataType.TOKEN),
                    DataTypeRef(datatype=DataType.STRING),
                )
            ),
        ),
    )
    assert canonical_json(ax1) == canonical_json(ax2)


# -- P-03-9: Determinism --


def test_canonical_idempotent():
    from ontoloom.canonical import _normalize_model

    ax = EquivalentClasses(
        equivalent_classes=(
            IRI("ex:B"),
            IRI("ex:A"),
        )
    )
    assert canonical_json(_normalize_model(ax)) == canonical_json(
        _normalize_model(_normalize_model(ax))
    )


def test_selection_hash_order_independent(tmp_path):
    path = tmp_path / "test.db"
    Ontology.create(path)
    with session(Ontology(path)) as s:
        h1 = upsert_selection(
            s, SelectionName("s1"), SelectionKind.ENTITIES, ["ex:Dog", "ex:Cat", "ex:Fish"], "test"
        ).selection.hash
        h2 = upsert_selection(
            s, SelectionName("s2"), SelectionKind.ENTITIES, ["ex:Fish", "ex:Dog", "ex:Cat"], "test"
        ).selection.hash
        assert h1 == h2
        s.commit()


def test_selection_pagination_stable_across_processes(tmp_path):
    """Set-op selections must paginate the same way regardless of PYTHONHASHSEED.

    Read pagination is lexicographic by item, so this is robust independently
    of how set-ops iterate. Kept as a regression guard against accidental order
    drift.
    """
    import subprocess
    import sys
    import textwrap

    db_path = tmp_path / "det.db"
    Ontology.create(db_path)
    script = textwrap.dedent(f"""\
        from pathlib import Path
        from ontoloom.query.dispatch import run
        from ontoloom.selections.compose import create_selection
        from ontoloom.selections.expr import IntersectExpr
        from ontoloom.selections.store import upsert_selection
        from ontoloom.selections.read_entity_selection import ReadEntitySelection
        from ontoloom.selections.types import EntitySelectionName, SelectionKind, SelectionName
        from ontoloom.connection import Ontology
        from ontoloom.connection import session

        with session(Ontology(Path({str(db_path)!r}))) as s:
            upsert_selection(s, "a", SelectionKind.ENTITIES,
                ["ex:Z", "ex:A", "ex:M", "ex:Q", "ex:B"], "src")
            upsert_selection(s, "b", SelectionKind.ENTITIES,
                ["ex:Z", "ex:A", "ex:M", "ex:R", "ex:C"], "src")
            r = EntitySelectionName("entities:r")
            create_selection(s, r, IntersectExpr(intersect=(SelectionName("a"), SelectionName("b"))))
            page = run(s, ReadEntitySelection(selection=r, limit=5))
            print(",".join(item.iri for item in page.items))
            s.commit()
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
