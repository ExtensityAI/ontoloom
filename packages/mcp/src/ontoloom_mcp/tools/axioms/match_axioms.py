from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.hashing import HashedAxiom
from ontoloom.patterns.store import match_axioms as core_match
from ontoloom.patterns.types import Pattern
from ontoloom.query._dispatch import run
from ontoloom.query._selection_ref import ResolvedSelection, resolve_selection
from ontoloom.query.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import SelectionKind, SelectionName, ShowFilter
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import (
    SELECT_INLINE_MAX,
    SELECT_PREVIEW,
    build_refs_per_axiom,
    format_axiom_listing,
    format_selection_result,
)
from ontoloom_mcp.components.selection_refs import SelectionRefParam
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import Limit, OntologyPath


def match_axioms(
    path: OntologyPath,
    pattern: Pattern,
    into: SelectionRefParam,
    within: SelectionRefParam | None = None,
    limit: Limit = 100,
):
    """Find axioms matching a structural pattern; save matches to an axiom selection.

    Pattern semantics:
    - Pattern objects mirror axiom structure, with `"?var"` for variables and `"*"`
      for wildcards in IRI positions. String IRIs in expression positions are
      shorthand for `X`.
    - Axiom-level patterns (e.g., `SubClassOfPattern`) match whole axioms of that type.
    - Expression-level patterns (e.g., `ObjectSomeValuesFromPattern`) match any axiom
      containing that expression at any depth.
    - Variables (`?name`) enforce cross-position equality: same variable in two
      positions means both must match the same value. Use
      `create_selection(entities_in=...)` afterwards to extract entities from matches.

    Args:
    - `pattern`: The pattern object to match.
    - `into`: Kind-prefixed name for the axiom selection to save results
      (e.g. `"axioms:my_matches"`).
    - `within`: Optional selection reference (e.g. `"axioms:my_sel"` or
      `"entities:my_ents"`) to restrict the search to.
    - `limit`: Cap on matches collected before iteration stops; raise to widen the scan.
    """
    if into.kind != SelectionKind.AXIOMS:
        msg = f"match_axioms produces an AXIOMS selection; got 'into={into}' with kind={into.kind}"
        raise ValueError(msg)

    ont = Ontology(path)
    with session(ont) as s:
        resolved_within = resolve_selection(s, within) if within is not None else None
        result = core_match(s, pattern, within=resolved_within, limit=limit)
        upserted = upsert_selection(
            s,
            SelectionName(into.bare_name),
            SelectionKind.AXIOMS,
            result.axiom_hashes,
            "match_axioms",
        )
        sel = upserted.selection

        truncated_hint = (
            f" (truncated at limit={limit}; raise it to see more)" if result.truncated else ""
        )
        header = f"{len(result.axiom_hashes)} axioms matched{truncated_hint}"

        if not result.axiom_hashes:
            s.commit()
            return f"{header} -> {dquoted(sel.locked)}."

        page_size = sel.size if sel.size <= SELECT_INLINE_MAX else SELECT_PREVIEW
        page = run(
            s,
            ReadAxiomSelection(
                selection=ResolvedSelection(kind=SelectionKind.AXIOMS, bare_name=str(sel.name)),
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
        page_text = format_axiom_listing(page_axioms, refs_per_axiom=refs_per_axiom)
        s.commit()

    return f"{header}. " + format_selection_result("axioms", upserted, page_text)


tool_match_axioms = create_tool(
    match_axioms,
    name="match_axioms",
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
)
