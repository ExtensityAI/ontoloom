from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.selections.expr import SetExpr
from ontoloom.selections.store import create_selection as core_create_selection
from ontoloom.transactions import session

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName


def create_selection(
    path: OntologyPath,
    name: SelectionName,
    expr: SetExpr,
):
    """Create a selection by evaluating a set-expression tree.

    `expr` is an object with exactly one of:

    - `{"union": [<operand>, ...]}` - items in any operand
    - `{"intersect": [<operand>, ...]}` - items in all operands (>= 2)
    - `{"diff": [<operand>, ...]}` - first operand minus the rest (>= 2)
    - `{"axioms_for": <operand>}` - axioms mentioning entities in the operand
    - `{"entities_in": <operand>, "field": <position>?}` - entities mentioned
      by axioms in the operand, optionally restricted to a structural slot
      (e.g. "sub_class", "filler")

    Each `<operand>` is either a saved selection name (bare string, e.g.
    `"my_sel"`) or another expression object. Operands compose:
    `{"union": [{"axioms_for": "ents1"}, {"axioms_for": "ents2"}]}` is one
    call. Set ops require all operands to evaluate to the same kind (axioms
    or entities); conversions (`axioms_for`, `entities_in`) transform kind.

    Overwrites if name exists.
    """
    ont = Ontology(path)
    with session(ont) as s:
        upserted = core_create_selection(s, name, expr)
        s.commit()

    sel = upserted.selection
    parts = [f"Selection {sel.locked!r}: {sel.size} {sel.kind}"]
    if upserted.previous_size is not None:
        parts.append(f"(overwrote previous: {upserted.previous_size} items)")
    return " ".join(parts)


tool_create_selection = create_tool(
    create_selection, name="create_selection", annotations=ToolAnnotations(idempotentHint=True)
)
