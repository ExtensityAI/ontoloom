from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.selections.compose import create_axiom_selection, create_entity_selection
from ontoloom.selections.expr import SetExpr
from ontoloom.selections.types import AxiomSelectionName, EntitySelectionName

from ontoloom_mcp.components.locking import format_locked_quoted
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def create_selection(
    path: OntologyPath,
    name: AxiomSelectionName | EntitySelectionName,
    expr: SetExpr,
):
    """Create a selection by evaluating a set-expression tree.

    `name` is a kind-prefixed reference (e.g. `"axioms:my_sel"` or
    `"entities:my_sel"`); the prefix must match the kind the expression
    evaluates to, or the call raises before any write.

    `expr` is an object with exactly one of:

    - `{"union": [<operand>, ...]}` - items in any operand
    - `{"intersect": [<operand>, ...]}` - items in all operands (>= 2)
    - `{"diff": [<operand>, ...]}` - first operand minus the rest (>= 2)
    - `{"axioms_for": <operand>}` - axioms mentioning entities in the operand
    - `{"entities_in": <operand>, "position": <position>?}` - entities mentioned
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
        if isinstance(name, AxiomSelectionName):
            ax = create_axiom_selection(s, name, expr)
            s.commit()
            sel_ax = ax.selection
            parts = [f"Selection {format_locked_quoted(sel_ax)}: {sel_ax.size} axioms"]

            if ax.previous_size is not None:
                parts.append(f"(overwrote previous: {ax.previous_size} items)")
            return " ".join(parts)

        ent = create_entity_selection(s, name, expr)
        s.commit()
        sel_ent = ent.selection
        parts = [f"Selection {format_locked_quoted(sel_ent)}: {sel_ent.size} entities"]

        if ent.previous_size is not None:
            parts.append(f"(overwrote previous: {ent.previous_size} items)")
        return " ".join(parts)


tool_create_selection = create_tool(
    create_selection, name="create_selection", annotations=ToolAnnotations(idempotentHint=True)
)
