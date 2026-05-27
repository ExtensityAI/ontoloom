"""Evaluate `AxiomSetExpr` / `EntitySetExpr` trees and persist the result."""

from collections.abc import Callable, Sequence

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
from ontoloom.utils import difference_ordered, dquoted, intersect_ordered, union_ordered


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


def _eval_axiom_expr(s: Session, expr: AxiomSetExpr) -> list[AxiomHash]:
    match expr:
        case AxiomSelectionName():
            if not axiom_selection_exists(s, expr.bare):
                raise SelectionNotFoundError(expr.bare)

            return get_axiom_selection_items(s, expr.bare)
        case AxiomUnionExpr():
            return _combine(s, expr.union, SetOp.UNION, _eval_axiom_expr)
        case AxiomIntersectExpr():
            return _combine(s, expr.intersect, SetOp.INTERSECTION, _eval_axiom_expr)
        case AxiomDiffExpr():
            return _combine(s, expr.diff, SetOp.DIFFERENCE, _eval_axiom_expr)
        case AxiomsForExpr():
            entity_items = _eval_entity_expr(s, expr.axioms_for)
            return _axioms_for(s, entity_items)
        case _:
            msg = f"Unknown AxiomSetExpr variant: {type(expr).__name__}"
            raise ValueError(msg)


def _eval_entity_expr(s: Session, expr: EntitySetExpr) -> list[IRI]:
    match expr:
        case EntitySelectionName():
            if not entity_selection_exists(s, expr.bare):
                raise SelectionNotFoundError(expr.bare)

            return get_entity_selection_items(s, expr.bare)
        case EntityUnionExpr():
            return _combine(s, expr.union, SetOp.UNION, _eval_entity_expr)
        case EntityIntersectExpr():
            return _combine(s, expr.intersect, SetOp.INTERSECTION, _eval_entity_expr)
        case EntityDiffExpr():
            return _combine(s, expr.diff, SetOp.DIFFERENCE, _eval_entity_expr)
        case EntitiesInExpr():
            axiom_items = _eval_axiom_expr(s, expr.entities_in)
            return _entities_in(s, axiom_items, expr.position)
        case _:
            msg = f"Unknown EntitySetExpr variant: {type(expr).__name__}"
            raise ValueError(msg)


def _combine[X, E: str](
    s: Session,
    operands: Sequence[X],
    op: SetOp,
    eval_fn: Callable[[Session, X], list[E]],
) -> list[E]:
    _check_arity(op, len(operands))
    results = [eval_fn(s, sub) for sub in operands]
    return _apply_set_op(results, op)


def _check_arity(op: SetOp, count: int):
    if count == 0:
        msg = f"{dquoted(op)} requires at least one operand."
        raise SelectionExprError(msg)

    if op in (SetOp.INTERSECTION, SetOp.DIFFERENCE) and count < 2:
        msg = f"{dquoted(op)} requires at least two operands; got {count}."
        raise SelectionExprError(msg)


def _apply_set_op[E: str](results: Sequence[Sequence[E]], op: SetOp) -> list[E]:
    match op:
        case SetOp.UNION:
            return union_ordered(*results)
        case SetOp.INTERSECTION:
            return intersect_ordered(results[0], *results[1:])
        case SetOp.DIFFERENCE:
            return difference_ordered(results[0], *results[1:])
        case _:
            msg = f"Unknown set operation: {op}"
            raise ValueError(msg)


def _axioms_for(s: Session, entity_iris: Sequence[IRI]) -> list[AxiomHash]:
    if not entity_iris:
        return []

    return run(s, ListAxiomHashes(constraints=(MentionsAny(iris=tuple(entity_iris)),)))


def _entities_in(
    s: Session, axiom_hashes: Sequence[AxiomHash], field: Position | None
) -> list[IRI]:
    if not axiom_hashes:
        return []

    constraints: list[EntityConstraint] = [MentionedIn(hashes=tuple(axiom_hashes))]

    if field is not None:
        constraints.append(InPositions(positions=(field,)))

    return run(s, ListEntities(constraints=tuple(constraints)))
