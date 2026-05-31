from mcp.types import ToolAnnotations
from ontoloom.axioms.reader import summarize_axioms
from ontoloom.axioms.types import AxiomSummary
from ontoloom.connection import Ontology, session
from ontoloom.entities.projections import find_top_entities_by_axiom_count
from ontoloom.entities.reader import (
    count_undeclared_entities,
    summarize_entities,
)
from ontoloom.entities.types import EntitySummary
from ontoloom.owl.iri import IRI
from ontoloom.prefixes.store import count_prefix_usage, list_prefixes
from ontoloom.prefixes.types import NamespaceIRI, PrefixName
from ontoloom.query.constraints import InAxiomSelection
from ontoloom.query.dispatch import resolve_within
from ontoloom.selections.store import get_axiom_selection, get_entity_selection
from ontoloom.selections.types import AxiomSelection, EntitySelection, SelectionName

from ontoloom_mcp.components.formatting import (
    Ref,
    build_refs,
    format_ref,
    format_within_scope,
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
        ax_summary = summarize_axioms(s, within=within)
        ent_summary = summarize_entities(s, within=within)
        prefix_map = list_prefixes(s)

        scope_meta: AxiomSelection | EntitySelection | None = None
        if within is not None:
            if isinstance(resolve_within(s, within), InAxiomSelection):
                scope_meta = get_axiom_selection(s, within)
            else:
                scope_meta = get_entity_selection(s, within)

        # `excl` matches `search_entities(declared=False)` (exclude_deprecated=True);
        # `incl` is the raw count for transparency.
        undeclared_excl = count_undeclared_entities(s, within, exclude_deprecated=True)
        undeclared_incl = count_undeclared_entities(s, within, exclude_deprecated=False)

        top_rows = find_top_entities_by_axiom_count(s, _TOP_ENTITIES)
        top_refs = build_refs(s, [iri for iri, _ in top_rows]) if top_rows else []

        prefix_usage = count_prefix_usage(s) if (within is None and prefix_map) else {}

        s.commit()

    parts: list[str] = []

    if scope_meta is not None:
        parts.append(f"{format_within_scope(scope_meta)}:")
        parts.append("")

    parts.append(_format_entity_summary(ent_summary))
    parts.append(_format_axiom_summary(ax_summary))

    if undeclared_incl > 0:
        base = (
            f"Undeclared references: {undeclared_excl} entities appear in axioms "
            f"without Declaration axioms"
        )
        if undeclared_incl != undeclared_excl:
            base += f" ({undeclared_incl} including deprecated)"
        parts.append(base + ".")

    if top_rows:
        parts.append(_format_top_entities(top_rows, top_refs))

    if within is None:
        parts.append(_format_prefix_block(prefix_map, prefix_usage))

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


def _format_top_entities(top_rows: list[tuple[IRI, int]], top_refs: list[Ref]):
    lines = [f"Top {len(top_rows)} entities by axiom count:"]
    for ref, (_, cnt) in zip(top_refs, top_rows, strict=True):
        lines.append(f"  {format_ref(ref)}: {cnt} axioms")
    return "\n".join(lines)


def _format_prefix_block(prefix_map: dict[PrefixName, NamespaceIRI], usage: dict[PrefixName, int]):
    if not prefix_map:
        return "No prefixes defined."
    lines = ["Prefixes:"]
    for name, iri in sorted(prefix_map.items()):
        lines.append(f"  {name}: -> {iri} ({usage.get(name, 0)} entities)")
    return "\n".join(lines)


tool_describe_ontology = create_tool(
    describe_ontology,
    name="describe_ontology",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
