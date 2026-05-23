"""Reusable preview renderers for selection-creating MCP tools."""

from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Session
from ontoloom.query.dispatch import run
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.store import AxiomUpsertResult
from ontoloom.selections.types import AxiomSelectionName, ShowFilter

from ontoloom_mcp.components.formatting import (
    SELECT_INLINE_MAX,
    SELECT_PREVIEW,
    build_refs_per_axiom,
    format_axiom_listing,
)


def format_axiom_selection_preview(
    s: Session, upserted: AxiomUpsertResult, limit: int | None = None
) -> str:
    """Render the head page of a just-upserted axiom selection.

    Small selections (size <= SELECT_INLINE_MAX) are shown in full; larger ones
    are capped at SELECT_PREVIEW. Pass `limit` to additionally cap the page
    size from above (used by `search_axioms`, whose `limit` parameter governs
    inline preview width).
    """
    sel = upserted.selection
    page_size = sel.size if sel.size <= SELECT_INLINE_MAX else SELECT_PREVIEW
    if limit is not None:
        page_size = min(page_size, limit)

    page = run(
        s,
        ReadAxiomSelection(
            selection=AxiomSelectionName(f"axioms:{sel.name}"),
            limit=page_size,
            offset=0,
            show=ShowFilter.ALL,
        ),
    )
    page_axioms = [
        HashedAxiom(axiom=item.axiom, hash=item.hash)
        for item in page.items
        if item.axiom is not None
    ]
    refs_per_axiom = build_refs_per_axiom(s, page_axioms)
    return format_axiom_listing(page_axioms, refs_per_axiom=refs_per_axiom)
