from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from ontoloom.ontology.models.literals import Annotation
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.formatting import format_axiom_listing
from ontoloom_mcp.components.types import OntologyPath


def _annotate_axiom(
    path: OntologyPath,
    axiom_hash: str,
    add_annotations: list[Annotation] | None = None,
    remove_annotations: list[Annotation] | None = None,
):
    """Add or remove annotations on an existing axiom. The axiom's hash does not change.

    Use `search_axioms` to find axiom hashes.
    """
    with OntologyStore(path) as store:
        try:
            result = store.annotate_axiom(
                axiom_hash,
                add_annotations=add_annotations,
                remove_annotations=remove_annotations,
            )
        except ValueError as e:
            raise ToolError(str(e)) from e
        listing = format_axiom_listing([result])
        n_add = len(add_annotations or [])
        n_remove = len(remove_annotations or [])
        return f"Updated annotations (+{n_add}, -{n_remove}):\n\n{listing}"


tool_annotate_axiom = Tool.from_function(_annotate_axiom, name="annotate_axiom")
