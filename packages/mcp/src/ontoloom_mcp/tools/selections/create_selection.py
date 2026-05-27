from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.selections.compose import create_selection_from_expr
from ontoloom.selections.expr import SetExpr
from ontoloom.selections.store import AxiomUpsertResult
from ontoloom.selections.types import SelectionName, WriteMode

from ontoloom_mcp.components.formatting import format_selection_ref
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def create_selection(
    path: OntologyPath,
    name: SelectionName,
    expr: SetExpr,
    mode: WriteMode = WriteMode.CREATE,
):
    """Create a selection by evaluating a set-expression tree.

    `name` is a bare selection name (e.g. `"my_sel"`). The selection's kind
    (axioms or entities) is inferred from `expr`. A name may exist as an axiom
    OR an entity selection, never both.

    `expr` is a bare selection name, or an object with exactly one of:

    - `{"union": [<operand>, ...]}` - items in any operand
    - `{"intersect": [<operand>, ...]}` - items in all operands (>= 2)
    - `{"diff": [<operand>, ...]}` - first operand minus the rest (>= 2)
    - `{"axioms_for": <operand>}` - axioms mentioning entities in the operand
      (operand must evaluate to entities)
    - `{"entities_in": <operand>, "position": <position>?}` - entities mentioned
      by axioms in the operand (operand must evaluate to axioms), optionally
      restricted to a structural slot (e.g. "sub_class", "filler")

    Each `<operand>` is a bare selection name or another expression object. Set
    ops require all operands to resolve to the same kind; `axioms_for`/`entities_in`
    flip the kind.

    `mode`: `create` (default) refuses if the name already exists; `replace` overwrites it.
    """
    ont = Ontology(path)

    with session(ont) as s:
        upserted = create_selection_from_expr(s, name, expr, mode=mode)
        s.commit()

    sel = upserted.selection
    kind_label = "axioms" if isinstance(upserted, AxiomUpsertResult) else "entities"
    parts = [f"Selection {format_selection_ref(sel)}: {sel.size} {kind_label}"]

    if upserted.previous_size is not None:
        parts.append(f"(overwrote previous: {upserted.previous_size} items)")

    return " ".join(parts)


tool_create_selection = create_tool(
    create_selection, name="create_selection", annotations=ToolAnnotations()
)
