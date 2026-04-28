from mcp.types import ToolAnnotations
from ontoloom.ontology import axioms, entities, prefixes, selections
from ontoloom.ontology.connection import Ontology

from ontoloom_mcp.components.formatting import (
    format_axiom_summary_from_counter,
    format_entity_summary,
    format_iri_with_label,
    lookup_labels,
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
        axiom_counts = axioms.summary(ont, within=within)
        total_entities, role_counts = entities.summary(ont, within=within)
        prefix_map = prefixes.list_all(ont)

        parts = []

        if within:
            sel = selections.get_info(ont, within)
            parts.append(f"Within selection {within!r} ({sel.kind}, sel@{sel.hash}):")
            parts.append("")

        parts.append(format_entity_summary(total_entities, role_counts))
        parts.append(format_axiom_summary_from_counter(axiom_counts))

        # Undeclared reference count
        declared_count = ont.conn.execute(
            "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE ae.role IS NOT NULL"
        ).fetchone()[0]
        undeclared = total_entities - declared_count
        if undeclared > 0:
            parts.append(
                f"Undeclared references: {undeclared} entities appear in axioms without Declaration axioms."
            )

        # Top entities by axiom count
        top_rows = ont.conn.execute(
            "SELECT ae.entity_iri, COUNT(DISTINCT ae.axiom_id) as cnt "
            "FROM axiom_entities ae "
            "GROUP BY ae.entity_iri "
            "ORDER BY cnt DESC "
            "LIMIT ?",
            (_TOP_ENTITIES,),
        ).fetchall()
        if top_rows:
            top_iris = [row[0] for row in top_rows]
            labels = lookup_labels(ont.conn, top_iris)
            top_lines = [f"Top {len(top_rows)} entities by axiom count:"]
            for iri, cnt in top_rows:
                top_lines.append(f"  {format_iri_with_label(iri, labels)}: {cnt} axioms")
            parts.append("\n".join(top_lines))

        # Prefixes with usage counts
        if not within:
            if prefix_map:
                usage = prefixes.usage_counts(ont)
                prefix_lines = ["Prefixes:"]
                for name, iri in sorted(prefix_map.items()):
                    count = usage.get(name, 0)
                    prefix_lines.append(f"  {name}: \u2192 {iri} ({count} entities)")
                parts.append("\n".join(prefix_lines))
            else:
                parts.append("No prefixes defined.")

        return "\n\n".join(parts)


tool_describe_ontology = create_tool(
    describe_ontology,
    name="describe_ontology",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
