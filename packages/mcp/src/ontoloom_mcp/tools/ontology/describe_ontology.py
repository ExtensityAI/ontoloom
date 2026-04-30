from mcp.types import ToolAnnotations
from ontoloom.ontology import axioms, entities, prefixes, selections
from ontoloom.ontology.connection import Ontology

from ontoloom_mcp.components.formatting import (
    format_axiom_summary,
    format_entity_summary,
    format_iri_with_label,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName

_TOP_ENTITIES = 10


def describe_ontology(path: OntologyPath, within: SelectionName | None = None):
    """Get entity counts, axiom counts, prefix mappings, and structural hubs.

    Start here. Shows ontology structure, prefix mappings with usage counts,
    top entities by axiom count, and undeclared reference count.

    Use `within` to restrict to a named selection.
    """
    with Ontology(path) as ont:
        axiom_summary = axioms.summary(ont, within=within)
        entity_summary = entities.summary(ont, within=within)
        prefix_map = prefixes.list_all(ont)

        parts = []

        if within:
            sel = selections.get(ont, within)
            parts.append(f"Within selection {within!r} ({sel.kind}, sel@{sel.hash}):")
            parts.append("")

        parts.append(format_entity_summary(entity_summary))
        parts.append(format_axiom_summary(axiom_summary))

        # Undeclared reference count
        declared = entities.declared_count(ont, within)
        undeclared = entity_summary.total - declared
        if undeclared > 0:
            parts.append(
                f"Undeclared references: {undeclared} entities appear in axioms without Declaration axioms."
            )

        # Top entities by axiom count
        top_rows = entities.top_by_axiom_count(ont, _TOP_ENTITIES)
        if top_rows:
            top_iris = [str(iri) for iri, _ in top_rows]
            labels = entities.lookup_labels(ont, top_iris)
            top_lines = [f"Top {len(top_rows)} entities by axiom count:"]
            for iri, cnt in top_rows:
                top_lines.append(f"  {format_iri_with_label(str(iri), labels)}: {cnt} axioms")
            parts.append("\n".join(top_lines))

        # Prefixes with usage counts
        if not within:
            if prefix_map:
                usage = prefixes.usage_counts(ont)
                prefix_lines = ["Prefixes:"]
                for name, iri in sorted(prefix_map.items()):
                    count = usage.get(name, 0)
                    prefix_lines.append(f"  {name}: -> {iri} ({count} entities)")
                parts.append("\n".join(prefix_lines))
            else:
                parts.append("No prefixes defined.")

        return "\n\n".join(parts)


tool_describe_ontology = create_tool(
    describe_ontology,
    name="describe_ontology",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
