from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.patterns import Pattern
from ontoloom.patterns.store import match_axioms as core_match
from ontoloom.selections.store import upsert_selection
from ontoloom.selections.types import SelectionKind

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import Limit, OntologyPath, SelectionName


def match_axioms(
    path: OntologyPath,
    pattern: Pattern,
    into: SelectionName,
    within: SelectionName | None = None,
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
    - `into`: Name for the axiom selection to save results.
    - `within`: Optional selection to restrict search to.
    - `limit`: Cap on matches collected before iteration stops; raise to widen the scan.
    """
    with Ontology(path) as ont:
        result = core_match(ont, pattern, within=within, limit=limit)
        upserted = upsert_selection(
            ont, into, SelectionKind.AXIOMS, result.axiom_hashes, "match_axioms"
        )

    truncated_hint = (
        f" (truncated at limit={limit}; raise it to see more)" if result.truncated else ""
    )
    sel = upserted.selection
    msg = f"{result.total} axioms matched{truncated_hint} -> {sel.locked!r} ({sel.size} items)"
    if upserted.previous_size is not None:
        msg += f" (was {upserted.previous_size})"
    return msg


tool_match_axioms = create_tool(
    match_axioms,
    name="match_axioms",
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
)
