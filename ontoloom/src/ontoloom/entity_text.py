"""Schema vocabulary and label lookups for the `entity_text` SQL table.

Both the axiom writer (`axioms.store`) and the readers (`entities.store`,
`selections.store`) depend on these names. Hosting them here keeps the
stores from reaching into each other and breaks what would otherwise be
a near-circular dependency.
"""

from collections.abc import Iterable

from ontoloom.connection import Session
from ontoloom.owl.iri import RDFS_LABEL

# Sentinel for `entity_text.property` rows that index an IRI's local-name
# (vs. real annotation-property values).
LOCAL_NAME_PROPERTY = "local_name"

_LABEL_BATCH_SIZE = 500


def lookup_entity_labels(s: Session, iris: Iterable[str]) -> dict[str, str | None]:
    """Return {iri: rdfs:label | None} for each IRI in the input."""
    iri_list = list(iris)
    result: dict[str, str | None] = dict.fromkeys(iri_list)
    for i in range(0, len(iri_list), _LABEL_BATCH_SIZE):
        batch = iri_list[i : i + _LABEL_BATCH_SIZE]
        ph = ",".join("?" for _ in batch)
        result.update(
            s.conn.execute(
                f"SELECT entity_iri, text FROM entity_text "
                f"WHERE entity_iri IN ({ph}) AND property = ?",
                (*batch, RDFS_LABEL),
            ).fetchall()
        )
    return result
