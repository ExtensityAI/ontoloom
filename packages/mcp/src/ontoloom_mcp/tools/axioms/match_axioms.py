from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.patterns.search import match_axioms as core_match
from ontoloom.patterns.types import Pattern
from ontoloom.selections.store import upsert_axiom_selection
from ontoloom.selections.types import SelectionName, WriteMode

from ontoloom_mcp.components.formatting import (
    MatchAxiomsSource,
    fetch_preview_data,
    format_selection_write,
    format_source,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import Limit, OntologyPath


def match_axioms(
    path: OntologyPath,
    pattern: Pattern,
    into: SelectionName,
    mode: WriteMode = WriteMode.CREATE,
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
    - `into`: Name for the axiom selection to save results (e.g. `"my_matches"`).
    - `mode`: `create` (default) refuses if the selection name already exists; `replace` overwrites it.
    - `within`: Optional selection name (axiom or entity) to restrict the search to.
    - `limit`: Cap on matches collected before iteration stops; preview is
      independently capped at PREVIEW_ROWS.
    """
    src = MatchAxiomsSource(within=within)

    ont = Ontology(path)
    with session(ont) as s:
        result = core_match(s, pattern, within=within, limit=limit)
        upserted = upsert_axiom_selection(
            s,
            into,
            result.axiom_hashes,
            format_source(src),
            mode=mode,
        )
        preview = fetch_preview_data(s, upserted)
        s.commit()

    return format_selection_write(
        upserted,
        preview,
        src,
        truncated_limit=limit if result.truncated else None,
    )


tool_match_axioms = create_tool(
    match_axioms,
    name="match_axioms",
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
)
