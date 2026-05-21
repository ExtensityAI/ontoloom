"""Schema vocabulary and writers for the `entity_text` SQL table.

The constants and writers live together so axiom-side mutation code does not
need to know what `entity_text.property` rows look like.
"""

from ontoloom.connection import Session
from ontoloom.owl.axioms import BaseAxiom
from ontoloom.owl.iri import IRI

# Sentinel for `entity_text.property` rows that index an IRI's local-name
# (vs. real annotation-property values).
LOCAL_NAME_PROPERTY = "local_name"

# Compact form of `owl:deprecated`. The codebase stores IRIs as CURIEs throughout.
OWL_DEPRECATED_PROPERTY = "owl:deprecated"


def record_local_name(s: Session, axiom_id: int, iri: IRI) -> None:
    """Index the local_name fragment of `iri` under axiom `axiom_id`."""
    local = iri.local_name
    if not local:
        return

    s.conn.execute(
        "INSERT INTO entity_text (axiom_id, entity_iri, text, property) VALUES (?, ?, ?, ?)",
        (axiom_id, str(iri), local, LOCAL_NAME_PROPERTY),
    )


def record_annotation_value(s: Session, axiom_id: int, axiom: BaseAxiom) -> None:
    """If `axiom` is an AnnotationAssertion with a string value, index it.

    Implemented in Task 2.4 once the writer is exposed; this stub raises so any
    accidental early caller fails loudly.
    """
    msg = "record_annotation_value: implemented in Task 2.4"
    raise NotImplementedError(msg)
