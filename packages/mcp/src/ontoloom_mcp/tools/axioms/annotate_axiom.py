from typing import Annotated

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.models.literals import Annotation
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.formatting import format_axiom_listing
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _annotate_axiom(
    path: OntologyPath,
    axiom_hash: Annotated[str, "Full or prefix hash of the axiom (from search_axioms output)"],
    add_annotations: list[Annotation] = [],  # noqa: B006
    remove_annotations: list[Annotation] = [],  # noqa: B006
):
    """Add or remove annotations on an existing axiom. The axiom's hash does not change.

    Use `search_axioms` to find axiom hashes. Both full hashes and unambiguous prefixes are accepted.
    """
    with OntologyStore(path) as store:
        result = store.annotate_axiom(
            axiom_hash,
            add_annotations=add_annotations or None,
            remove_annotations=remove_annotations or None,
        )
        listing = format_axiom_listing([result])
        n_add = len(add_annotations)
        n_remove = len(remove_annotations)
        return f"Updated annotations (+{n_add}, -{n_remove}):\n\n{listing}"


tool_annotate_axiom = Tool.from_function(
    _annotate_axiom,
    name="annotate_axiom",
    annotations=ToolAnnotations(idempotentHint=True),
)
