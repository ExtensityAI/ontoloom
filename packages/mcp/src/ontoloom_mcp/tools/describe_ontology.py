from collections import Counter

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.index.builder import build_index
from ontoloom.core.ontology.index.models import Role

from ontoloom_mcp.components.formatting import format_axiom_summary
from ontoloom_mcp.components.ontology_file import OntologyPath, open_ontology

_ROLE_ORDER = list(Role)


def _format_entity_summary(role_counts: Counter[Role], total: int) -> str:
    rows = sorted(_ROLE_ORDER, key=lambda r: (-role_counts[r], r))
    lines = [f"{total} entities total"]
    lines.extend(f"  {role_counts[r]} {r}" for r in rows)
    return "\n".join(lines)


def _describe_ontology(path: OntologyPath):
    """Get entity and axiom count statistics for an ontology."""
    with open_ontology(path) as (ontology, _):
        index = build_index(ontology)
        role_counts: Counter[Role] = Counter()
        for entry in index.entities.values():
            for role in entry.roles:
                role_counts[role] += 1
        entity_summary = _format_entity_summary(role_counts, len(index.entities))
        axiom_summary = format_axiom_summary(ontology.axioms)
        return f"{entity_summary}\n\n{axiom_summary}"


tool_describe_ontology = Tool.from_function(
    _describe_ontology,
    name="describe_ontology",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
