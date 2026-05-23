from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.selections.compose import create_axiom_selection, create_entity_selection
from ontoloom.selections.expr import (
    AxiomSetExpr,
    EntitySetExpr,
    is_axiom_set_expr,
    is_entity_set_expr,
)
from ontoloom.selections.types import AxiomSelectionName, EntitySelectionName, SelectionExprError
from ontoloom.utils import dquoted

from ontoloom_mcp.components.locking import format_locked_quoted
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def create_selection(
    path: OntologyPath,
    name: AxiomSelectionName | EntitySelectionName,
    expr: AxiomSetExpr | EntitySetExpr,
):
    """Create a selection by evaluating a set-expression tree.

    `name` is a kind-prefixed reference (e.g. `"axioms:my_sel"` or
    `"entities:my_sel"`). `expr` must produce the matching kind:
    `AxiomSetExpr` if `name` starts with `axioms:`, `EntitySetExpr` if it
    starts with `entities:`. Leaves of `expr` are themselves kind-prefixed
    selection references.

    `expr` is an object with exactly one of:

    - `{"union": [<operand>, ...]}` - items in any operand
    - `{"intersect": [<operand>, ...]}` - items in all operands (>= 2)
    - `{"diff": [<operand>, ...]}` - first operand minus the rest (>= 2)
    - `{"axioms_for": <entity-operand>}` - axioms mentioning entities in the
      operand (produces axioms; operand must be an `EntitySetExpr`)
    - `{"entities_in": <axiom-operand>, "position": <position>?}` - entities
      mentioned by axioms in the operand (produces entities; operand must be
      an `AxiomSetExpr`), optionally restricted to a structural slot
      (e.g. "sub_class", "filler")

    Each `<operand>` is either a kind-prefixed selection name (e.g.
    `"axioms:my_sel"` / `"entities:my_sel"`) or another expression object of
    the matching kind. Set ops (`union`, `intersect`, `diff`) require all
    operands to be the same kind as the enclosing tree; the cross-kind
    operators (`axioms_for`, `entities_in`) flip the kind.

    Overwrites if name exists.
    """
    ont = Ontology(path)
    with session(ont) as s:
        if isinstance(name, AxiomSelectionName):
            if not is_axiom_set_expr(expr):
                msg = f"`name` {dquoted(name)} expects an AxiomSetExpr; got {type(expr).__name__}."
                raise SelectionExprError(msg)
            ax = create_axiom_selection(s, name, expr)
            s.commit()
            sel_ax = ax.selection
            parts = [f"Selection {format_locked_quoted(sel_ax)}: {sel_ax.size} axioms"]

            if ax.previous_size is not None:
                parts.append(f"(overwrote previous: {ax.previous_size} items)")
            return " ".join(parts)

        if not is_entity_set_expr(expr):
            msg = f"`name` {dquoted(name)} expects an EntitySetExpr; got {type(expr).__name__}."
            raise SelectionExprError(msg)
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
