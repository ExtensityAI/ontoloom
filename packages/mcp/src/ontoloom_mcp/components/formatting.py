"""Compact formatting for MCP output."""

from __future__ import annotations

from collections import Counter
from typing import cast, get_args

from ontoloom.core.ontology.models.axioms import AnnotationAssertion, Axiom
from ontoloom.core.ontology.models.literals import IRI, LangLiteral, TypedLiteral

from ontoloom_mcp.components.hashing import HashedAxiom

_DEFAULT_LANG = "en"


def format_annotation_value(value: str | TypedLiteral | LangLiteral) -> str:
    """Format an annotation value compactly, suppressing @en."""
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, LangLiteral):
        tag = "" if value.lang == _DEFAULT_LANG else f"@{value.lang}"
        return f'"{value.value}"{tag}'
    return str(value)


def format_annotation_compact(ann: AnnotationAssertion) -> str:
    """Format an annotation as 'property: value'."""
    return f"{ann.property}: {format_annotation_value(ann.value)}"


type DiffEntry = tuple[str, HashedAxiom]


def format_diff(entries: list[DiffEntry], summary: str) -> str:
    """Format a diff with a summary and tagged axiom lines (with hash prefixes)."""
    changes = "\n".join(f"{tag} [{ha.prefix}] {ha.axiom}" for tag, ha in entries)
    return f"{summary}\n\n```diff\n{changes}\n```"


AXIOM_TYPE_NAMES: tuple[str] = tuple(
    cls.model_fields["type"].default for cls in get_args(get_args(Axiom)[0])
)


def format_roles(roles: set) -> str:
    return ", ".join(sorted(str(r) for r in roles)) or "none"


def format_axiom_summary(axioms: tuple[Axiom, ...]) -> str:
    """Render axiom count statistics: total + breakdown by type, sorted descending."""
    counts = Counter(a.type for a in axioms)
    rows = sorted(AXIOM_TYPE_NAMES, key=lambda t: (-counts[t], t))
    lines = [f"{len(axioms)} axioms total"]
    lines.extend(f"  {counts[t]} {t}" for t in rows)
    return "\n".join(lines)


def format_axiom_listing(hashed: list[HashedAxiom]) -> str:
    """Render axioms as compact lines with shortest-unique hash prefixes."""
    if not hashed:
        return ""
    return "\n".join(f"[{ha.prefix}] {ha.axiom}" for ha in hashed)


def format_entity_inspect(
    iri: IRI,
    roles: set,
    annotations: list[HashedAxiom],
    axiom_counts: Counter[str],
) -> str:
    """Format a single entity's inspect output: roles, annotations, axiom counts."""
    lines = [f"{iri} ({format_roles(roles)})", ""]

    if annotations:
        lines.append("Annotations:")
        lines.extend(
            f"  [{ha.prefix}] {format_annotation_compact(cast('AnnotationAssertion', ha.axiom))}"
            for ha in annotations
        )
        lines.append("")

    total = sum(axiom_counts.values())
    if total:
        lines.append(f"Axioms (asserted): {total}")
        for typ, count in axiom_counts.most_common():
            lines.append(f"  {count} {typ}")

    return "\n".join(lines).rstrip()


def format_search_axioms_page(
    hashed: list[HashedAxiom],
    total: int,
    offset: int,
) -> str:
    """Format a paginated axiom listing with total count."""
    if not hashed:
        return "0 results."

    end = offset + len(hashed)
    header = f"Showing {offset + 1}-{end} of {total} results:"
    listing = format_axiom_listing(hashed)
    return f"{header}\n\n{listing}"
