"""Compact formatting for MCP output."""

from collections import Counter

from ontoloom.core.ontology.models.base import EntityType
from ontoloom.core.ontology.models.literals import IRI
from ontoloom.core.ontology.store import EntityInfo, HashedAxiom


def format_roles(roles: set[EntityType]) -> str:
    return ", ".join(sorted(str(r) for r in roles)) or "none"


def format_diff(entries: list[tuple[str, HashedAxiom]], summary: str) -> str:
    """Format a diff with a summary and tagged axiom lines."""
    changes = "\n".join(f"{tag} [{ha.hash[:8]}] {ha.axiom}" for tag, ha in entries)
    return f"{summary}\n\n```diff\n{changes}\n```"


def format_axiom_listing(axioms: list[HashedAxiom]) -> str:
    """Render axioms as compact lines with hash prefixes."""
    if not axioms:
        return ""
    return "\n".join(f"[{ha.hash[:8]}] {ha.axiom}" for ha in axioms)


def format_search_axioms_page(axioms: list[HashedAxiom], total: int, offset: int) -> str:
    """Format a paginated axiom listing with total count."""
    if not axioms:
        return "0 results."
    end = offset + len(axioms)
    header = f"Showing {offset + 1}-{end} of {total} results:"
    listing = format_axiom_listing(axioms)
    return f"{header}\n\n{listing}"


def format_entity_inspect(iri: IRI, info: EntityInfo) -> str:
    """Format a single entity's inspect output."""
    lines = [f"{iri} ({format_roles(info.roles)})", ""]

    if info.annotations:
        lines.append("Annotations:")
        lines.extend(f'  {ann.property}: "{ann.value}"' for ann in info.annotations)
        lines.append("")

    total = sum(info.axiom_counts.values())
    if total:
        lines.append(f"Axioms (asserted): {total}")
        for typ, count in info.axiom_counts.most_common():
            lines.append(f"  {count} {typ}")

    return "\n".join(lines).rstrip()


def format_entity_summary(total: int, role_counts: Counter[str]) -> str:
    """Format entity count summary."""
    lines = [f"{total} entities total"]
    for role, count in role_counts.most_common():
        lines.append(f"  {count} {role}")
    return "\n".join(lines)


def format_axiom_summary_from_counter(counts: Counter[str]) -> str:
    """Format axiom count summary from a Counter."""
    total = sum(counts.values())
    lines = [f"{total} axioms total"]
    for typ, count in counts.most_common():
        lines.append(f"  {count} {typ}")
    return "\n".join(lines)
