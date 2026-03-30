"""Compact formatting for MCP output."""

from __future__ import annotations

from collections import Counter
from typing import get_args

from ontoloom.core.ontology.models.axioms import Axiom

from ontoloom_mcp.hashing import HashedAxiom

type DiffEntry = tuple[str, HashedAxiom]  # ("+", ha) or ("=", ha) or ("-", ha)


def format_diff(entries: list[DiffEntry], summary: str) -> str:
    """Format a diff with a summary and tagged axiom lines (with hash prefixes)."""
    changes = "\n".join(f"{tag} [{ha.prefix}] {ha.axiom}" for tag, ha in entries)
    return f"{summary}\n\n```diff\n{changes}\n```"


AXIOM_TYPE_NAMES: tuple[str] = tuple(
    cls.model_fields["type"].default for cls in get_args(get_args(Axiom)[0])
)
"""Names of all axiom types"""


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
