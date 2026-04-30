from ontoloom.ontology.canonical import axiom_hash
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.errors import InternalError
from ontoloom.ontology.extract import iter_axiom_entities
from ontoloom.ontology.models.axioms import AnnotationAssertion
from ontoloom.ontology.models.base import BaseAxiom
from ontoloom.ontology.models.literals import IRI, Annotation, EntityType, LangLiteral, TypedLiteral

# A: bad var name - what is this?
_LOCAL_NAME = "local_name"


def _extract_annotation_value(value: IRI | TypedLiteral | LangLiteral):
    # A: bad function name, very unclear what this is
    if isinstance(value, IRI):
        return str(value)
    return value.value


def insert_axiom(ont: Ontology, axiom: BaseAxiom, *, ignore_existing: bool = False) -> int | None:
    """INSERT axiom row and populate indexes. Returns axiom_id, or None if already existed (ignore_existing=True only)."""
    h = axiom_hash(axiom)
    json_data = axiom.model_dump_json()
    verb = (
        "INSERT OR IGNORE" if ignore_existing else "INSERT"
    )  # A: when do we not IGNORE EXISTING? same hash = same axiom, so this is always idempotent. no need to change this. or is there a reason?
    cursor = ont.conn.execute(
        f"{verb} INTO axioms (hash, type, data) VALUES (?, ?, jsonb(?))",
        (h, axiom.type_, json_data),
    )
    if ignore_existing and cursor.rowcount == 0:
        return None
    axiom_id = cursor.lastrowid
    if axiom_id is None:
        msg = "INSERT succeeded but lastrowid is None"  # A: can this ever happen?
        raise InternalError(msg)
    populate(ont, axiom, axiom_id)
    return axiom_id


def repopulate_axiom_text(
    ont: Ontology, axiom_id: int, annotations: tuple[Annotation, ...]
) -> None:
    # A: is axiom_id best way to refer to axiom here? why is this not done via hash? any good reason? is it because hash takes a lot of space?
    """Rebuild axiom_text index rows for a single axiom after an annotation change."""
    ont.conn.execute("DELETE FROM axiom_text WHERE axiom_id = ?", (axiom_id,))
    rows = [
        (axiom_id, _extract_annotation_value(ann.value), str(ann.property)) for ann in annotations
    ]
    if rows:
        ont.conn.executemany(
            "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
            rows,
        )


def populate(ont: Ontology, axiom: BaseAxiom, axiom_id: int) -> None:
    # A: again, naming is bad, return type hints, what does this do, is this internal only?
    """Populate index tables (axiom_entities, entity_text, axiom_text) for a new axiom."""
    entity_rows = []
    text_rows = []
    seen_iris: set[str] = set()

    # A: huge function, seems like it has too many responsibilities

    for iri, role, position in iter_axiom_entities(axiom):
        iri_str = str(iri)
        role_val = role.value if isinstance(role, EntityType) else role
        pos_val = position.value if position is not None else None
        entity_rows.append((axiom_id, iri_str, role_val, pos_val))
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
        "INSERT INTO axiom_entities (axiom_id, entity_iri, role, position) VALUES (?, ?, ?, ?)",
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
