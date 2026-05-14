from mcp.types import ToolAnnotations
from ontoloom.axioms.store import axiom_summary as compute_axiom_summary
from ontoloom.connection import Ontology, session
from ontoloom.entities.store import (
    entity_summary as compute_entity_summary,
)
from ontoloom.entities.store import (
    top_entities_by_axiom_count,
    undeclared_entity_count,
)
from ontoloom.prefixes.store import list_prefixes, prefix_usage_counts
from ontoloom.query._selection_ref import resolve_selection
from ontoloom.selections.store import get_selection
from ontoloom.selections.types import SelectionName
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import (
    build_refs,
    format_axiom_summary,
    format_entity_summary,
    format_ref,
)
from ontoloom_mcp.components.selection_refs import SelectionRefParam
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath

_TOP_ENTITIES = 10


def describe_ontology(path: OntologyPath, within: SelectionRefParam | None = None):
    """Get entity counts, axiom counts, prefix mappings, and structural hubs.

    Start here. Shows ontology structure, prefix mappings with usage counts,
    top entities by axiom count, and undeclared reference count.

    Use `within` (e.g. `"axioms:my_sel"` or `"entities:my_ents"`) to restrict
    to a named selection.
    """
    ont = Ontology(path)
    with session(ont) as s:
        resolved = resolve_selection(s, within) if within is not None else None
        ax_summary = compute_axiom_summary(s, within=resolved)
        ent_summary = compute_entity_summary(s, within=resolved)
        prefix_map = list_prefixes(s)

        parts = []

        if resolved is not None:
            sel = get_selection(s, SelectionName(resolved.bare_name))
            parts.append(f"Within selection {dquoted(sel.locked)} ({sel.kind}):")
            parts.append("")

        parts.append(format_entity_summary(ent_summary))
        parts.append(format_axiom_summary(ax_summary))

        # Undeclared reference count.
        # `excl` matches `search_entities(declared=False)`'s default
        # (exclude_deprecated=True); `incl` is the raw count for transparency.
        undeclared_excl = undeclared_entity_count(s, resolved, exclude_deprecated=True)
        undeclared_incl = undeclared_entity_count(s, resolved, exclude_deprecated=False)
        if undeclared_incl > 0:
            base = (
                f"Undeclared references: {undeclared_excl} entities appear in axioms "
                f"without Declaration axioms"
            )
            if undeclared_incl != undeclared_excl:
                base += f" ({undeclared_incl} including deprecated)"
            parts.append(base + ".")

        # Top entities by axiom count
        top_rows = top_entities_by_axiom_count(s, _TOP_ENTITIES)
        if top_rows:
            top_refs = build_refs(s, [iri for iri, _ in top_rows])
            top_lines = [f"Top {len(top_rows)} entities by axiom count:"]
            for ref, (_, cnt) in zip(top_refs, top_rows, strict=True):
                top_lines.append(f"  {format_ref(ref)}: {cnt} axioms")
            parts.append("\n".join(top_lines))

        # Prefixes with usage counts
        if resolved is None:
            if prefix_map:
                usage = prefix_usage_counts(s)
                prefix_lines = ["Prefixes:"]
                for name, iri in sorted(prefix_map.items()):
                    count = usage.get(name, 0)
                    prefix_lines.append(f"  {name}: -> {iri} ({count} entities)")
                parts.append("\n".join(prefix_lines))
            else:
                parts.append("No prefixes defined.")

        s.commit()

    return "\n\n".join(parts)


tool_describe_ontology = create_tool(
    describe_ontology,
    name="describe_ontology",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
