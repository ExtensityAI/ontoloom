from collections import Counter

from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.literals import IRI
from ontoloom.ontology.types import EntityInfo, EntityMatch, HashedAxiom

SELECT_PREVIEW = 5
SELECT_INLINE_MAX = 20


def format_roles(roles: set[EntityType]) -> str:
    return ", ".join(sorted(str(r) for r in roles)) or "none"


def format_diff(entries: list[tuple[str, HashedAxiom]], summary: str) -> str:
    changes = "\n".join(f"{tag} [{ha.hash[:8]}] {ha.axiom}" for tag, ha in entries)
    return f"{summary}\n\n```diff\n{changes}\n```"


def format_axiom_listing(axioms: list[HashedAxiom]) -> str:
    if not axioms:
        return ""
    return "\n".join(f"[{ha.hash[:8]}] {ha.axiom}" for ha in axioms)


def format_search_axioms_page(axioms: list[HashedAxiom], total: int, offset: int) -> str:
    if not axioms:
        return "0 results."
    end = offset + len(axioms)
    header = f"Showing {offset + 1}-{end} of {total} results:"
    listing = format_axiom_listing(axioms)
    return f"{header}\n\n{listing}"


def format_entity_inspect(iri: IRI, info: EntityInfo) -> str:
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
    lines = [f"{total} entities total"]
    for role, count in role_counts.most_common():
        lines.append(f"  {count} {role}")
    return "\n".join(lines)


def format_axiom_summary_from_counter(counts: Counter[str]) -> str:
    total = sum(counts.values())
    lines = [f"{total} axioms total"]
    for typ, count in counts.most_common():
        lines.append(f"  {count} {typ}")
    return "\n".join(lines)


def format_selection_result(
    kind_label: str,
    select: str,
    content_hash: str,
    cardinality: int,
    old_cardinality: int | None,
    page_text: str,
) -> str:
    parts = [f"{cardinality} {kind_label} \u2192 {select!r} (sel@{content_hash})."]
    if old_cardinality is not None:
        parts.append(f"Overwrote previous ({old_cardinality} items).")

    if cardinality <= SELECT_INLINE_MAX:
        parts.append("")
        parts.append(page_text)
    else:
        parts.append(f"Preview (first {SELECT_PREVIEW}):")
        parts.append("")
        parts.append(page_text)
        parts.append(f"\nUse read_selection(name={select!r}) to browse all {cardinality} results.")

    return "\n".join(parts)


def format_entity_search_page(matches: list[EntityMatch], total: int, offset: int) -> str:
    end = offset + len(matches)
    lines = [f"Showing {offset + 1}-{end} of {total} entities:"]
    lines.append("")
    for m in matches:
        role_str = format_roles(m.roles)
        label = ""
        for ann in m.annotations:
            if str(ann.property) == "rdfs:label":
                label = f' "{ann.value}"'
                break
        lines.append(f"  {m.iri} ({role_str}){label}")
        lines.extend(
            f'    {ann.property}: "{ann.value}"'
            for ann in m.annotations
            if str(ann.property) != "rdfs:label"
        )
    return "\n".join(lines)
