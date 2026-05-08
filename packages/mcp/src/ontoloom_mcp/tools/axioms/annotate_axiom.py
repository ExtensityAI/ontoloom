from mcp.types import ToolAnnotations
from ontoloom.axioms.store import annotate_axiom as core_annotate_axiom
from ontoloom.connection import Ontology
from ontoloom.entities.store import lookup_entity_labels as core_lookup_entity_labels
from ontoloom.owl.annotations import Annotation
from ontoloom.transactions import session

from ontoloom_mcp.components.formatting import (
    format_axiom_listing,
    walk_unique_iris,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import HexPrefix, OntologyPath


def annotate_axiom(
    path: OntologyPath,
    axiom_hash: HexPrefix,
    add_annotations: list[Annotation] | None = None,
    remove_annotations: list[Annotation] | None = None,
):
    """Add or remove annotations on an existing axiom. The axiom's hash does not change.

    Args:
    - `axiom_hash`: Full hash or unambiguous prefix. Use `match_axioms` to find one.
    - `add_annotations`: Annotations to add (deduplicated against existing).
    - `remove_annotations`: Annotations to remove (no-op if absent).
    """
    ont = Ontology(path)
    with session(ont) as s:
        result = core_annotate_axiom(
            s,
            axiom_hash,
            add_annotations=add_annotations,
            remove_annotations=remove_annotations,
        )
        iris = walk_unique_iris(result.axiom)
        labels = core_lookup_entity_labels(s, iris)
        listing = format_axiom_listing([result], labels=labels, iris_per_axiom=[iris])
        n_add = len(add_annotations or [])
        n_remove = len(remove_annotations or [])
        s.commit()

    return f"Updated annotations (+{n_add}, -{n_remove}):\n\n{listing}"


tool_annotate_axiom = create_tool(
    annotate_axiom, name="annotate_axiom", annotations=ToolAnnotations(idempotentHint=True)
)
