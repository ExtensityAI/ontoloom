from mcp.types import ToolAnnotations
from ontoloom.axioms.types import HashedAxiom
from ontoloom.connection import Ontology, session
from ontoloom.patterns.search import match_axioms as core_match
from ontoloom.patterns.types import Pattern
from ontoloom.query.dispatch import run
from ontoloom.selections.persistence import upsert_selection
from ontoloom.selections.read_axiom_selection import ReadAxiomSelection
from ontoloom.selections.types import (
    AxiomSelectionName,
    SelectionKind,
    SelectionRef,
    ShowFilter,
)

from ontoloom_mcp.components.formatting import (
    SELECT_INLINE_MAX,
    SELECT_PREVIEW,
    build_refs_per_axiom,
    format_axiom_listing,
    format_selection_result,
)
from ontoloom_mcp.components.locking import format_locked_quoted
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import Limit, OntologyPath


def match_axioms(
    path: OntologyPath,
    pattern: Pattern,
    into: AxiomSelectionName,
    within: SelectionRef | None = None,
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
    ont = Ontology(path)
    with session(ont) as s:
        result = core_match(s, pattern, within=within, limit=limit)
        upserted = upsert_selection(
            s,
            into.bare,
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
            return f"{header} -> {format_locked_quoted(sel)}."

        page_size = sel.size if sel.size <= SELECT_INLINE_MAX else SELECT_PREVIEW
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
        page_text = format_axiom_listing(page_axioms, refs_per_axiom=refs_per_axiom)
        s.commit()

    return f"{header}. " + format_selection_result("axioms", upserted, page_text)


tool_match_axioms = create_tool(
    match_axioms,
    name="match_axioms",
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
)
