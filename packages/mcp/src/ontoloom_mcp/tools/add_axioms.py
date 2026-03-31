from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.operations import add_axioms

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.hashing import compute_hashes
from ontoloom_mcp.components.ontology_file import OntologyPath, open_ontology
from ontoloom_mcp.models.axioms import Axiom as MCPAxiom
from ontoloom_mcp.models.converters import convert_axiom


def _add_axioms(path: OntologyPath, axioms: list[MCPAxiom]):
    """Add axioms to an existing ontology file. Duplicates are skipped. Returns a diff: '+' = added, '=' = skipped."""
    converted = [convert_axiom(a) for a in axioms]
    with open_ontology(path, write=True) as (ontology, save):
        new_ontology, result = add_axioms(ontology, converted)

        if result.added:
            save(new_ontology)

        hashed = {ha.axiom: ha for ha in compute_hashes(new_ontology.axioms)}
        added_set = set(result.added)
        entries = [("+" if a in added_set else "=", hashed[a]) for a in converted]
        return format_diff(
            entries,
            f"Added {len(result.added)}, skipped {len(result.skipped)}, total {len(new_ontology.axioms)} axioms.",
        )


tool_add_axioms = Tool.from_function(
    _add_axioms, name="add_axioms", annotations=ToolAnnotations(idempotentHint=True)
)
