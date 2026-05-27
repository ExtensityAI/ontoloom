from mcp.types import ToolAnnotations
from ontoloom.axioms.reader import axiom_summary as compute_axiom_summary
from ontoloom.axioms.types import AxiomSummary
from ontoloom.connection import Ontology, session
from ontoloom.entities.projections import top_entities_by_axiom_count
from ontoloom.entities.reader import (
    entity_summary as compute_entity_summary,
)
from ontoloom.entities.reader import (
    undeclared_entity_count,
)
from ontoloom.entities.types import EntitySummary
from ontoloom.prefixes.store import list_prefixes, prefix_usage_counts
from ontoloom.query.constraints import InAxiomSelection
from ontoloom.query.dispatch import resolve_within
from ontoloom.selections.store import get_axiom_selection, get_entity_selection
from ontoloom.selections.types import SelectionName

from ontoloom_mcp.components.formatting import (
    build_refs,
    format_ref,
    format_selection_ref,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath

_TOP_ENTITIES = 10


def describe_ontology(path: OntologyPath, within: SelectionName | None = None):
    """Get entity counts, axiom counts, prefix mappings, and structural hubs.

    Start here. Shows ontology structure, prefix mappings with usage counts,
    top entities by axiom count, and undeclared reference count.

    Use `within` (e.g. `"my_sel"` or `"my_ents"`) to restrict to a named
    selection.
    """
    ont = Ontology(path)
    with session(ont) as s:
        ax_summary = compute_axiom_summary(s, within=within)
        ent_summary = compute_entity_summary(s, within=within)
        prefix_map = list_prefixes(s)

        parts = []

        if within is not None:
            if isinstance(resolve_within(s, within), InAxiomSelection):
                sel_ax = get_axiom_selection(s, within)
                parts.append(f"Within selection {format_selection_ref(sel_ax)} (axioms):")
            else:
                sel_ent = get_entity_selection(s, within)
                parts.append(f"Within selection {format_selection_ref(sel_ent)} (entities):")
            parts.append("")

        parts.append(_format_entity_summary(ent_summary))
        parts.append(_format_axiom_summary(ax_summary))

        # `excl` matches `search_entities(declared=False)` (exclude_deprecated=True);
        # `incl` is the raw count for transparency.
        undeclared_excl = undeclared_entity_count(s, within, exclude_deprecated=True)
        undeclared_incl = undeclared_entity_count(s, within, exclude_deprecated=False)
        if undeclared_incl > 0:
            base = (
                f"Undeclared references: {undeclared_excl} entities appear in axioms "
                f"without Declaration axioms"
            )
            if undeclared_incl != undeclared_excl:
                base += f" ({undeclared_incl} including deprecated)"
            parts.append(base + ".")

        top_rows = top_entities_by_axiom_count(s, _TOP_ENTITIES)
        if top_rows:
            top_refs = build_refs(s, [iri for iri, _ in top_rows])
            top_lines = [f"Top {len(top_rows)} entities by axiom count:"]
            for ref, (_, cnt) in zip(top_refs, top_rows, strict=True):
                top_lines.append(f"  {format_ref(ref)}: {cnt} axioms")
            parts.append("\n".join(top_lines))

        if within is None:
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


def _format_entity_summary(summary: EntitySummary):
    lines = [f"{summary.total} entities total"]
    role_total = sum(summary.by_role.values())
    if role_total != summary.total:
        # Per-role counts can sum higher (an entity punned across roles is counted
        # in each) or lower (an entity with no role is omitted). Flag so the LLM
        # doesn't expect strict arithmetic.
        lines.append("By role (entities can have multiple roles, e.g. punning):")
    else:
        lines.append("By role:")
    for role, count in summary.by_role.most_common():
        lines.append(f"  {count} {role}")
    return "\n".join(lines)


def _format_axiom_summary(summary: AxiomSummary):
    lines = [f"{summary.total} axioms total"]
    for typ, count in summary.by_type.most_common():
        lines.append(f"  {count} {typ}")
    return "\n".join(lines)


tool_describe_ontology = create_tool(
    describe_ontology,
    name="describe_ontology",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
