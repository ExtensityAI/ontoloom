"""Tests for the ListAxiomHashes query."""

from ontoloom.axioms.store import add_axioms
from ontoloom.hashing import AxiomHash, HashedAxiom
from ontoloom.owl.annotations import Annotation
from ontoloom.owl.axioms import Declaration, SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import AxiomTag, EntityType
from ontoloom.query.constraints import (
    AlwaysFalse,
    HasAnyAnnotation,
    MentionsAny,
    TextMatchKind,
    WithAnnotationText,
    WithTypes,
)
from ontoloom.query.list_axiom_hashes import ListAxiomHashes

# -- render snapshots --


def test_render_no_constraints_no_pagination():
    compiled = (ListAxiomHashes(constraints=())).render()
    assert compiled.sql == "SELECT a.hash FROM axioms a WHERE 1 ORDER BY a.hash"
    assert compiled.params == ()


def test_render_with_of_types():
    compiled = (ListAxiomHashes(constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)),))).render()
    assert compiled.sql == ("SELECT a.hash FROM axioms a WHERE a.type IN (?) ORDER BY a.hash")
    assert compiled.params == ("Declaration",)


def test_render_limit_only():
    compiled = (ListAxiomHashes(constraints=(), limit=10)).render()
    assert compiled.sql == "SELECT a.hash FROM axioms a WHERE 1 ORDER BY a.hash LIMIT ?"
    assert compiled.params == (10,)


def test_render_limit_and_offset():
    compiled = (ListAxiomHashes(constraints=(), limit=10, offset=5)).render()
    assert compiled.sql == "SELECT a.hash FROM axioms a WHERE 1 ORDER BY a.hash LIMIT ? OFFSET ?"
    assert compiled.params == (10, 5)


def test_render_limit_with_zero_offset_omits_offset_clause():
    compiled = (ListAxiomHashes(constraints=(), limit=10, offset=0)).render()
    assert compiled.sql == "SELECT a.hash FROM axioms a WHERE 1 ORDER BY a.hash LIMIT ?"
    assert compiled.params == (10,)


def test_render_constraints_and_pagination():
    compiled = (
        ListAxiomHashes(
            constraints=(MentionsAny(iris=(IRI("ex:A"),)),),
            limit=3,
            offset=1,
        )
    ).render()
    assert compiled.sql == (
        "SELECT a.hash FROM axioms a WHERE "
        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
        "WHERE ae_m.axiom_id = a.id AND ae_m.entity_iri IN (?)) "
        "ORDER BY a.hash LIMIT ? OFFSET ?"
    )
    assert compiled.params == ("ex:A", 3, 1)


def test_render_always_false_short_circuits():
    compiled = (ListAxiomHashes(constraints=(AlwaysFalse(),), limit=5)).render()
    assert compiled.sql == "SELECT a.hash FROM axioms a WHERE 0 ORDER BY a.hash LIMIT ?"
    assert compiled.params == (5,)


def test_render_always_includes_order_by():
    for q in [
        ListAxiomHashes(constraints=()),
        ListAxiomHashes(constraints=(WithTypes(tags=(AxiomTag.DECLARATION,)),)),
        ListAxiomHashes(constraints=(), limit=10),
        ListAxiomHashes(constraints=(), limit=10, offset=5),
        ListAxiomHashes(constraints=(AlwaysFalse(),)),
    ]:
        assert "ORDER BY a.hash" in q.render().sql


# -- _run integration --


def test_run_empty_ontology(s):
    assert (ListAxiomHashes(constraints=()))._run(s) == []


def test_run_lists_in_hash_order(s):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Zebra")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Antelope")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Mongoose")),
    ]
    add_axioms(s, decls)

    result = (ListAxiomHashes(constraints=()))._run(s)
    expected = sorted([HashedAxiom.of(d).hash for d in decls])
    assert result == expected


def test_run_returns_axiom_hash_typed_values(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    result = (ListAxiomHashes(constraints=()))._run(s)
    assert len(result) == 1
    assert isinstance(result[0], AxiomHash)


def test_run_pagination_stable(s):
    decls = [Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:C{i}")) for i in range(6)]
    add_axioms(s, decls)

    page1 = (ListAxiomHashes(constraints=(), limit=2))._run(s)
    page2 = (ListAxiomHashes(constraints=(), limit=2, offset=2))._run(s)

    assert len(page1) == 2
    assert len(page2) == 2
    assert set(page1).isdisjoint(page2)


def test_run_pagination_full_walk(s):
    decls = [
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:A")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:B")),
        Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:C")),
    ]
    add_axioms(s, decls)

    full = (ListAxiomHashes(constraints=()))._run(s)
    paged = (
        (ListAxiomHashes(constraints=(), limit=1))._run(s)
        + (ListAxiomHashes(constraints=(), limit=1, offset=1))._run(s)
        + (ListAxiomHashes(constraints=(), limit=1, offset=2))._run(s)
    )
    assert paged == full


def test_run_filter_by_of_types(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")),
        ],
    )
    result = (ListAxiomHashes(constraints=(WithTypes(tags=(AxiomTag.SUB_CLASS_OF,)),)))._run(s)
    expected_hash = HashedAxiom.of(
        SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal"))
    ).hash
    assert result == [expected_hash]


def test_run_always_false(s):
    add_axioms(s, [Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog"))])
    assert (ListAxiomHashes(constraints=(AlwaysFalse(),)))._run(s) == []


# -- WithAnnotationText render --


def test_render_with_annotation_text_substring_no_properties():
    compiled = ListAxiomHashes(
        constraints=(WithAnnotationText(text="TODO"),),
    ).render()
    assert "EXISTS (SELECT 1 FROM axiom_text at" in compiled.sql
    assert "INSTR(LOWER(at.text), ?) > 0" in compiled.sql
    assert "at.property IN" not in compiled.sql
    assert compiled.params == ("todo",)


def test_render_with_annotation_text_substring_with_properties():
    compiled = ListAxiomHashes(
        constraints=(WithAnnotationText(text="TODO", properties=(IRI("ex:p1"), IRI("ex:p2"))),),
    ).render()
    assert "at.property IN (?,?)" in compiled.sql
    assert "INSTR(LOWER(at.text), ?) > 0" in compiled.sql
    assert compiled.params == (IRI("ex:p1"), IRI("ex:p2"), "todo")


def test_render_with_annotation_text_exact_no_properties():
    compiled = ListAxiomHashes(
        constraints=(WithAnnotationText(text="TODO", match_kind=TextMatchKind.EXACT),),
    ).render()
    assert "LOWER(at.text) = ?" in compiled.sql
    assert "INSTR" not in compiled.sql
    assert "at.property IN" not in compiled.sql
    assert compiled.params == ("todo",)


def test_render_with_annotation_text_exact_with_properties():
    compiled = ListAxiomHashes(
        constraints=(
            WithAnnotationText(
                text="TODO",
                properties=(IRI("ex:p1"),),
                match_kind=TextMatchKind.EXACT,
            ),
        ),
    ).render()
    assert "at.property IN (?)" in compiled.sql
    assert "LOWER(at.text) = ?" in compiled.sql
    assert "INSTR" not in compiled.sql
    assert compiled.params == (IRI("ex:p1"), "todo")


# -- WithAnnotationText run --


def _comment(text: str) -> Annotation:
    return Annotation(property=IRI("rdfs:comment"), value=LangLiteral(value=text))


def _label(text: str) -> Annotation:
    return Annotation(property=IRI("rdfs:label"), value=LangLiteral(value=text))


def test_run_with_annotation_text_substring_matches_partial(s):
    matching = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("this is a TODO note"),),
    )
    other = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("unrelated content"),),
    )
    add_axioms(s, [matching, other])

    result = (ListAxiomHashes(constraints=(WithAnnotationText(text="TODO"),)))._run(s)
    assert result == [HashedAxiom.of(matching).hash]


def test_run_with_annotation_text_exact_no_substring(s):
    exact = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO"),),
    )
    superstring = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("TODO and more"),),
    )
    add_axioms(s, [exact, superstring])

    result = (
        ListAxiomHashes(
            constraints=(WithAnnotationText(text="TODO", match_kind=TextMatchKind.EXACT),),
        )
    )._run(s)
    assert result == [HashedAxiom.of(exact).hash]


def test_run_with_annotation_text_restricts_to_properties(s):
    commented = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("X"),),
    )
    labelled = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_label("X"),),
    )
    add_axioms(s, [commented, labelled])

    result = (
        ListAxiomHashes(
            constraints=(WithAnnotationText(text="X", properties=(IRI("rdfs:comment"),)),),
        )
    )._run(s)
    assert result == [HashedAxiom.of(commented).hash]


def test_run_with_annotation_text_empty_result(s):
    add_axioms(
        s,
        [
            SubClassOf(
                sub_class=IRI("ex:Dog"),
                super_class=IRI("ex:Animal"),
                annotations=(_comment("hello"),),
            ),
        ],
    )
    result = (ListAxiomHashes(constraints=(WithAnnotationText(text="nonexistent"),)))._run(s)
    assert result == []


# -- HasAnyAnnotation --


def test_render_has_any_annotation():
    compiled = ListAxiomHashes(
        constraints=(HasAnyAnnotation(properties=(IRI("ex:p1"), IRI("ex:p2"))),),
    ).render()
    assert (
        "EXISTS (SELECT 1 FROM axiom_text at WHERE at.axiom_id = a.id AND at.property IN (?,?))"
    ) in compiled.sql
    assert compiled.params == (IRI("ex:p1"), IRI("ex:p2"))


def test_run_has_any_annotation_existence(s):
    sourced = SubClassOf(
        sub_class=IRI("ex:Dog"),
        super_class=IRI("ex:Animal"),
        annotations=(
            Annotation(property=IRI("rdfs:isDefinedBy"), value=LangLiteral(value="imported")),
        ),
    )
    commented = SubClassOf(
        sub_class=IRI("ex:Cat"),
        super_class=IRI("ex:Animal"),
        annotations=(_comment("doc"),),
    )
    unannotated = SubClassOf(
        sub_class=IRI("ex:Fox"),
        super_class=IRI("ex:Animal"),
    )
    add_axioms(s, [sourced, commented, unannotated])

    result = (
        ListAxiomHashes(
            constraints=(HasAnyAnnotation(properties=(IRI("rdfs:isDefinedBy"),)),),
        )
    )._run(s)
    assert result == [HashedAxiom.of(sourced).hash]
