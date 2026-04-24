from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.extract import iter_axiom_entities
from ontoloom.ontology.models.axioms import AnnotationAssertion, Axiom
from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.literals import IRI, LangLiteral, TypedLiteral

_LOCAL_NAME = "local_name"


def _extract_annotation_value(value: IRI | TypedLiteral | LangLiteral):
    if isinstance(value, IRI):
        return str(value)
    return value.value


def populate(ont: Ontology, axiom: Axiom, axiom_id: int) -> None:
    """Populate index tables (axiom_entities, entity_text, axiom_text) for a new axiom."""
    entity_rows = []
    text_rows = []
    seen_iris: set[str] = set()

    for iri, role in iter_axiom_entities(axiom):
        iri_str = str(iri)
        role_val = role.value if isinstance(role, EntityType) else role
        entity_rows.append((axiom_id, iri_str, role_val))
        if iri_str not in seen_iris:
            seen_iris.add(iri_str)
            text_rows.append((axiom_id, iri_str, iri.local_name, _LOCAL_NAME))

    if isinstance(axiom, AnnotationAssertion):
        text_rows.append(
            (
                axiom_id,
                str(axiom.subject),
                _extract_annotation_value(axiom.value),
                str(axiom.property),
            )
        )

    ont.conn.executemany(
        "INSERT INTO axiom_entities (axiom_id, entity_iri, role) VALUES (?, ?, ?)",
        entity_rows,
    )
    ont.conn.executemany(
        "INSERT INTO entity_text (axiom_id, entity_iri, text, property) VALUES (?, ?, ?, ?)",
        text_rows,
    )

    axiom_text_rows = [
        (axiom_id, _extract_annotation_value(ann.value), str(ann.property))
        for ann in axiom.annotations
    ]
    if axiom_text_rows:
        ont.conn.executemany(
            "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
            axiom_text_rows,
        )
