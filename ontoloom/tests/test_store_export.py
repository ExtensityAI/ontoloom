"""JSONL export: format, byte-determinism, round-trip."""

import json

import pytest
from ontoloom.axioms.store import add_axioms
from ontoloom.export import export_to_jsonl
from ontoloom.hashing import HashedAxiom
from ontoloom.owl.axioms import (
    AnnotationAssertion,
    Axiom,
    Declaration,
    SubClassOf,
)
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import LangLiteral
from ontoloom.owl.markers import EntityType
from pydantic import TypeAdapter


@pytest.fixture()
def populated(s):
    add_axioms(
        s,
        [
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Dog")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Cat")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Animal")),
            Declaration(entity_type=EntityType.OBJECT_PROPERTY, iri=IRI("ex:hasOwner")),
            Declaration(entity_type=EntityType.CLASS, iri=IRI("other:Fish")),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Dog"),
                value=LangLiteral(value="Dog"),
            ),
            AnnotationAssertion(
                property=IRI("rdfs:label"),
                subject=IRI("ex:Cat"),
                value=LangLiteral(value="Cat"),
            ),
            SubClassOf(
                sub_class=IRI("ex:Dog"),
                super_class=IRI("ex:Animal"),
            ),
        ],
    )
    return s


def test_export_jsonl(populated, tmp_path):
    export_path = tmp_path / "export.jsonl"
    result = export_to_jsonl(populated, export_path)
    assert result.exported == 8
    assert result.skipped == 0

    lines = export_path.read_text().strip().split("\n")
    assert len(lines) == 9  # 1 header + 8 axioms

    header = json.loads(lines[0])
    assert header["format"] == "ontoloom-jsonl"
    assert "format_version" in header

    for line in lines[1:]:
        obj = json.loads(line)
        # axioms serialize with their structural fields (no `type` discriminator field)
        assert "annotations" in obj


def test_export_jsonl_hash_roundtrip(populated, tmp_path):
    original_hashes = {r[0] for r in populated.conn.execute("SELECT hash FROM axioms")}

    export_path = tmp_path / "export.jsonl"
    export_to_jsonl(populated, export_path)

    lines = export_path.read_text().strip().split("\n")
    adapter = TypeAdapter(Axiom)
    for line in lines[1:]:  # skip header
        parsed = adapter.validate_json(line)
        assert HashedAxiom.of(parsed).hash in original_hashes


def test_export_jsonl_byte_identical(populated, tmp_path):
    p1 = tmp_path / "a.jsonl"
    p2 = tmp_path / "b.jsonl"
    export_to_jsonl(populated, p1)
    export_to_jsonl(populated, p2)
    # Header lines differ (exported_at timestamp); axiom lines must be deterministic.
    axiom_lines_1 = p1.read_text().splitlines()[1:]
    axiom_lines_2 = p2.read_text().splitlines()[1:]
    assert axiom_lines_1 == axiom_lines_2


def test_unicode_iri_roundtrip(s, tmp_path):
    ax = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Ångström"))
    add_axioms(s, [ax])
    h = HashedAxiom.of(ax).hash

    export_path = tmp_path / "uni.jsonl"
    export_to_jsonl(s, export_path)

    adapter = TypeAdapter(Axiom)
    lines = export_path.read_text().strip().split("\n")
    parsed = adapter.validate_json(lines[1])  # lines[0] is the header
    assert HashedAxiom.of(parsed).hash == h
