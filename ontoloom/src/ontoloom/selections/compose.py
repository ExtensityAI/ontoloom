"""Evaluate `SetExpr` trees and persist the result as a new selection."""

from collections.abc import Sequence

from ontoloom.axioms.hashing import AxiomHash
from ontoloom.connection import Session
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import Position
from ontoloom.query.constraints import (
    EntityConstraint,
    InPositions,
    MentionedIn,
    MentionsAny,
)
from ontoloom.query.dispatch import run
from ontoloom.query.list_axiom_hashes import ListAxiomHashes
from ontoloom.query.list_entities import ListEntities
from ontoloom.selections.expr import (
    AxiomsForExpr,
    DiffExpr,
    EntitiesInExpr,
    IntersectExpr,
    SetExpr,
    SetOperand,
    UnionExpr,
)
from ontoloom.selections.persistence import UpsertResult, get_selection, upsert_selection
from ontoloom.selections.types import (
    SelectionExprError,
    SelectionKind,
    SelectionKindMismatchError,
    SelectionName,
    SelectionRef,
    SetOp,
)
from ontoloom.utils import dquoted


def create_selection(
    s: Session, name: SelectionRef, expr: SetExpr, *, source: str = ""
) -> UpsertResult:
    """Create a selection by evaluating a SetExpr tree.

    Raises `SelectionKindMismatchError` if the ref's kind (from its prefix)
    disagrees with the kind the SetExpr evaluates to.
    """
    items, kind = _eval_expr(s, expr)
    if kind != name.kind:
        raise SelectionKindMismatchError(name.bare, name.kind, kind)

    auto_source = source or str(expr)
    return upsert_selection(s, name.bare, kind, items, auto_source)


def _eval_expr(s: Session, expr: SetOperand) -> tuple[Sequence[str], SelectionKind]:
    if isinstance(expr, str):
        sel = get_selection(s, SelectionName(expr))
        items = [
            r[0]
            for r in s.conn.execute(
                "SELECT item FROM selection_items WHERE selection_name = ? ORDER BY id",
                (expr,),
            )
        ]
        return items, sel.kind

    if isinstance(expr, UnionExpr):
        return _eval_set_op(s, expr.union, SetOp.UNION)
    if isinstance(expr, IntersectExpr):
        return _eval_set_op(s, expr.intersect, SetOp.INTERSECTION)
    if isinstance(expr, DiffExpr):
        return _eval_set_op(s, expr.diff, SetOp.DIFFERENCE)

    if isinstance(expr, AxiomsForExpr):
        items, kind = _eval_expr(s, expr.axioms_for)
        if kind != SelectionKind.ENTITIES:
            msg = f"`axioms_for` requires an entity expression; operand is {kind}."
            raise SelectionExprError(msg)
        return _axioms_for(s, items), SelectionKind.AXIOMS

    if isinstance(expr, EntitiesInExpr):
        items, kind = _eval_expr(s, expr.entities_in)
        if kind != SelectionKind.AXIOMS:
            msg = f"`entities_in` requires an axiom expression; operand is {kind}."
            raise SelectionExprError(msg)
        return _entities_in(s, items, expr.position), SelectionKind.ENTITIES

    msg = f"Unknown SetExpr variant: {type(expr).__name__}"
    raise ValueError(msg)


def _eval_set_op(
    s: Session, operands: Sequence[SetOperand], op: SetOp
) -> tuple[Sequence[str], SelectionKind]:
    if not operands:
        msg = f"{dquoted(op)} requires at least one operand."
        raise SelectionExprError(msg)
    if op in (SetOp.INTERSECTION, SetOp.DIFFERENCE) and len(operands) < 2:
        msg = f"{dquoted(op)} requires at least two operands; got {len(operands)}."
        raise SelectionExprError(msg)

    results = [_eval_expr(s, sub) for sub in operands]
    kinds = {kind for _, kind in results}
    if len(kinds) > 1:
        msg = f"Cannot {op}: all operands must be the same kind. Got: {sorted(kinds)}"
        raise SelectionExprError(msg)
    kind = kinds.pop()

    match op:
        case SetOp.UNION:
            items_set: set[str] = set()
            for op_items, _ in results:
                items_set |= set(op_items)
        case SetOp.INTERSECTION:
            items_set = set(results[0][0])
            for op_items, _ in results[1:]:
                items_set &= set(op_items)
        case SetOp.DIFFERENCE:
            items_set = set(results[0][0])
            for op_items, _ in results[1:]:
                items_set -= set(op_items)
        case _:
            msg = f"Unknown set operation: {op}"
            raise ValueError(msg)

    return sorted(items_set), kind


def _axioms_for(s: Session, entity_iris: Sequence[str]) -> list[AxiomHash]:
    if not entity_iris:
        return []
    return run(
        s,
        ListAxiomHashes(
            constraints=(MentionsAny(iris=tuple(IRI(i) for i in entity_iris)),),
        ),
    )


def _entities_in(s: Session, axiom_hashes: Sequence[str], field: Position | None) -> list[IRI]:
    if not axiom_hashes:
        return []
    constraints: list[EntityConstraint] = [
        MentionedIn(hashes=tuple(AxiomHash(h) for h in axiom_hashes))
    ]
    if field is not None:
        constraints.append(InPositions(positions=(field,)))
    return run(s, ListEntities(constraints=tuple(constraints)))
