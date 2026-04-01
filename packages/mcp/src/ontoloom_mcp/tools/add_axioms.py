from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.models.axioms import Axiom
from ontoloom.core.ontology.operations import add_axioms

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.hashing import compute_hashes
from ontoloom_mcp.components.ontology_file import OntologyPath, open_ontology


def _add_axioms(path: OntologyPath, axioms: list[Axiom]):
    """Add axioms to an existing ontology file. Duplicates are skipped. Returns a diff: `+` = added, `=` = skipped."""
    with open_ontology(path, write=True) as (ontology, save):
        new_ontology, result = add_axioms(ontology, axioms)

        if result.added:
            save(new_ontology)

        hashed = {ha.axiom: ha for ha in compute_hashes(new_ontology.axioms)}
        added_set = set(result.added)
        entries = [("+" if a in added_set else "=", hashed[a]) for a in axioms]
        return format_diff(
            entries,
            f"Added {len(result.added)}, skipped {len(result.skipped)}, total {len(new_ontology.axioms)} axioms.",
        )


tool_add_axioms = Tool.from_function(
    _add_axioms, name="add_axioms", annotations=ToolAnnotations(idempotentHint=True)
)
