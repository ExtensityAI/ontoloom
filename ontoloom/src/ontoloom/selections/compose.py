"""Evaluate `AxiomSetExpr` / `EntitySetExpr` trees and persist the result."""

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
    AxiomDiffExpr,
    AxiomIntersectExpr,
    AxiomSetExpr,
    AxiomsForExpr,
    AxiomUnionExpr,
    EntitiesInExpr,
    EntityDiffExpr,
    EntityIntersectExpr,
    EntitySetExpr,
    EntityUnionExpr,
)
from ontoloom.selections.store import (
    AxiomUpsertResult,
    EntityUpsertResult,
    axiom_selection_exists,
    entity_selection_exists,
    get_axiom_selection_items,
    get_entity_selection_items,
    upsert_axiom_selection,
    upsert_entity_selection,
)
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
    SelectionExprError,
    SelectionNotFoundError,
    SetOp,
    WriteMode,
)
from ontoloom.utils import dquoted


def create_axiom_selection(
    s: Session,
    name: AxiomSelectionName,
    expr: AxiomSetExpr,
    *,
    source: str = "",
    mode: WriteMode = WriteMode.CREATE,
) -> AxiomUpsertResult:
    """Create an axiom selection by evaluating an `AxiomSetExpr` tree."""
    items = _eval_axiom_expr(s, expr)
    auto_source = source or str(expr)
    return upsert_axiom_selection(s, name.bare, items, auto_source, mode=mode)


def create_entity_selection(
    s: Session,
    name: EntitySelectionName,
    expr: EntitySetExpr,
    *,
    source: str = "",
    mode: WriteMode = WriteMode.CREATE,
) -> EntityUpsertResult:
    """Create an entity selection by evaluating an `EntitySetExpr` tree."""
    items = _eval_entity_expr(s, expr)
    auto_source = source or str(expr)
    return upsert_entity_selection(s, name.bare, items, auto_source, mode=mode)


def _eval_axiom_expr(s: Session, expr: AxiomSetExpr) -> list[str]:
    match expr:
        case AxiomSelectionName():
            if not axiom_selection_exists(s, expr.bare):
                raise SelectionNotFoundError(expr.bare)
            return list(get_axiom_selection_items(s, expr.bare))
        case AxiomUnionExpr():
            return _combine_axioms(s, expr.union, SetOp.UNION)
        case AxiomIntersectExpr():
            return _combine_axioms(s, expr.intersect, SetOp.INTERSECTION)
        case AxiomDiffExpr():
            return _combine_axioms(s, expr.diff, SetOp.DIFFERENCE)
        case AxiomsForExpr():
            entity_items = _eval_entity_expr(s, expr.axioms_for)
            return list(_axioms_for(s, entity_items))
        case _:
            msg = f"Unknown AxiomSetExpr variant: {type(expr).__name__}"
            raise ValueError(msg)


def _eval_entity_expr(s: Session, expr: EntitySetExpr) -> list[str]:
    match expr:
        case EntitySelectionName():
            if not entity_selection_exists(s, expr.bare):
                raise SelectionNotFoundError(expr.bare)
            return list(get_entity_selection_items(s, expr.bare))
        case EntityUnionExpr():
            return _combine_entities(s, expr.union, SetOp.UNION)
        case EntityIntersectExpr():
            return _combine_entities(s, expr.intersect, SetOp.INTERSECTION)
        case EntityDiffExpr():
            return _combine_entities(s, expr.diff, SetOp.DIFFERENCE)
        case EntitiesInExpr():
            axiom_items = _eval_axiom_expr(s, expr.entities_in)
            return list(_entities_in(s, axiom_items, expr.position))
        case _:
            msg = f"Unknown EntitySetExpr variant: {type(expr).__name__}"
            raise ValueError(msg)


def _combine_axioms(s: Session, operands: Sequence[AxiomSetExpr], op: SetOp) -> list[str]:
    _check_arity(op, len(operands))
    results = [_eval_axiom_expr(s, sub) for sub in operands]
    return sorted(_apply_set_op(results, op))


def _combine_entities(s: Session, operands: Sequence[EntitySetExpr], op: SetOp) -> list[str]:
    _check_arity(op, len(operands))
    results = [_eval_entity_expr(s, sub) for sub in operands]
    return sorted(_apply_set_op(results, op))


def _check_arity(op: SetOp, count: int):
    if count == 0:
        msg = f"{dquoted(op)} requires at least one operand."
        raise SelectionExprError(msg)

    if op in (SetOp.INTERSECTION, SetOp.DIFFERENCE) and count < 2:
        msg = f"{dquoted(op)} requires at least two operands; got {count}."
        raise SelectionExprError(msg)


def _apply_set_op(results: Sequence[Sequence[str]], op: SetOp) -> set[str]:
    match op:
        case SetOp.UNION:
            items: set[str] = set()
            for op_items in results:
                items |= set(op_items)
            return items
        case SetOp.INTERSECTION:
            items = set(results[0])
            for op_items in results[1:]:
                items &= set(op_items)
            return items
        case SetOp.DIFFERENCE:
            items = set(results[0])
            for op_items in results[1:]:
                items -= set(op_items)
            return items
        case _:
            msg = f"Unknown set operation: {op}"
            raise ValueError(msg)


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
