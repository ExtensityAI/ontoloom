from mcp.types import ToolAnnotations
from ontoloom.ontology import axioms, entities, prefixes, selections
from ontoloom.ontology.connection import Ontology

from ontoloom_mcp.components.formatting import (
    format_axiom_summary_from_counter,
    format_entity_summary,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName


def describe_ontology(path: OntologyPath, within: SelectionName | None = None):
    """Get entity counts, axiom counts, and prefix mappings for an ontology.

    - `within`: Scope to a named selection. Within an entity selection: count those
      entities and their axioms. Within an axiom selection: count those axioms and
      the entities they mention.
    """
    with Ontology(path) as ont:
        axiom_counts = axioms.summary(ont, within_selection=within)
        total_entities, role_counts = entities.summary(ont, within_selection=within)
        prefix_map = prefixes.list_all(ont)

        parts = []

        if within:
            sel = selections.get_info(ont, within)
            parts.append(f"Scoped to selection {within!r} ({sel.kind}, sel@{sel.hash}):")
            parts.append("")

        parts.append(format_entity_summary(total_entities, role_counts))
        parts.append(format_axiom_summary_from_counter(axiom_counts))

        if not within:
            if prefix_map:
                prefix_lines = ["Prefixes:"]
                for name, iri in sorted(prefix_map.items()):
                    prefix_lines.append(f"  {name}: \u2192 {iri}")
                parts.append("\n".join(prefix_lines))
            else:
                parts.append("No prefixes defined.")

        return "\n\n".join(parts)


tool_describe_ontology = create_tool(
    describe_ontology,
    name="describe_ontology",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
