from mcp.types import ToolAnnotations
from ontoloom.ontology import axioms
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.literals import Annotation

from ontoloom_mcp.components.formatting import format_axiom_listing
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import HexPrefix, OntologyPath


def annotate_axiom(
    path: OntologyPath,
    axiom_hash: HexPrefix,
    add_annotations: list[Annotation] | None = None,
    remove_annotations: list[Annotation] | None = None,
):
    """Add or remove annotations on an existing axiom. The axiom's hash does not change.

    Use `search_axioms` to find axiom hashes. Both full hashes and unambiguous prefixes are accepted.
    """
    with Ontology(path) as ont:
        result = axioms.annotate(
            ont,
            axiom_hash,
            add_annotations=add_annotations,
            remove_annotations=remove_annotations,
        )
        listing = format_axiom_listing([result])
        n_add = len(add_annotations or [])
        n_remove = len(remove_annotations or [])
        return f"Updated annotations (+{n_add}, -{n_remove}):\n\n{listing}"


tool_annotate_axiom = create_tool(
    annotate_axiom, name="annotate_axiom", annotations=ToolAnnotations(idempotentHint=True)
)
