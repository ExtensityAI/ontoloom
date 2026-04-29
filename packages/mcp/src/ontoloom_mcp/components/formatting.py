import sqlite3
from collections import Counter

from ontoloom.ontology.extract import iter_axiom_entities
from ontoloom.ontology.models.literals import IRI, EntityType
from ontoloom.ontology.types import EntityInfo, EntityMatch, HashedAxiom

SELECT_PREVIEW = 5
SELECT_INLINE_MAX = 20

_LABEL_BATCH_SIZE = 500


def lookup_labels(conn: sqlite3.Connection, iris: list[str]):
    """Look up rdfs:label for a list of IRIs. Returns {iri: label | None}."""
    result: dict[str, str | None] = dict.fromkeys(iris)
    for i in range(0, len(iris), _LABEL_BATCH_SIZE):
        batch = iris[i : i + _LABEL_BATCH_SIZE]
        ph = ",".join("?" for _ in batch)
        result.update(
            conn.execute(
                f"SELECT entity_iri, text FROM entity_text "
                f"WHERE entity_iri IN ({ph}) AND property = 'rdfs:label'",
                batch,
            ).fetchall()
        )
    return result


def collect_axiom_iris(axioms: list[HashedAxiom]):
    """Extract unique entity IRIs from a list of hashed axioms."""
    seen: set[str] = set()
    for ha in axioms:
        for iri, _role, _pos in iter_axiom_entities(ha.axiom):
            seen.add(str(iri))
    return list(seen)


def format_iri_with_label(iri: str, labels: dict[str, str | None]):
    label = labels.get(iri)
    return f'{iri} "{label}"' if label else iri


def format_roles(roles: set[EntityType]):
    return ", ".join(sorted(str(r) for r in roles)) or "none"


def _format_axiom_line(ha: HashedAxiom, labels: dict[str, str | None]):
    """Format a single axiom line with an inline label hint when labels are available."""
    line = f"[{ha.hash[:8]}] {ha.axiom}"
    if not labels:
        return line
    hints = []
    seen: set[str] = set()
    for iri, _role, _pos in iter_axiom_entities(ha.axiom):
        iri_str = str(iri)
        if iri_str in seen:
            continue
        seen.add(iri_str)
        label = labels.get(iri_str)
        if label:
            hints.append(f'{iri} "{label}"')
    if hints:
        line += "  # " + ", ".join(hints)
    return line


def format_diff(
    entries: list[tuple[str, HashedAxiom]],
    summary: str,
    labels: dict[str, str | None] | None = None,
):
    lb = labels or {}
    changes = "\n".join(f"{tag} {_format_axiom_line(ha, lb)}" for tag, ha in entries)
    return f"{summary}\n\n```diff\n{changes}\n```"


def format_axiom_listing(
    axioms: list[HashedAxiom],
    labels: dict[str, str | None] | None = None,
):
    if not axioms:
        return ""
    lb = labels or {}
    return "\n".join(_format_axiom_line(ha, lb) for ha in axioms)


def format_entity_inspect(
    iri: IRI,
    info: EntityInfo,
    labels: dict[str, str | None] | None = None,
):
    lb = labels or {}
    header = format_iri_with_label(str(iri), lb)
    lines = [f"{header} ({format_roles(info.roles)})", ""]

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


def format_entity_summary(total: int, role_counts: Counter[str]):
    lines = [f"{total} entities total"]
    for role, count in role_counts.most_common():
        lines.append(f"  {count} {role}")
    return "\n".join(lines)


def format_axiom_summary_from_counter(counts: Counter[str]):
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
):
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
        parts.append(
            f"\nUse `read_selection(name={select!r})` to browse all {cardinality} results."
        )

    return "\n".join(parts)


def format_entity_search_page(matches: list[EntityMatch], total: int, offset: int):
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
