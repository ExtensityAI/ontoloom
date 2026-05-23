"""Evaluate `SetExpr` trees and persist the result as a new selection."""

from collections.abc import Sequence
from enum import StrEnum

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
    SelectionName,
    SelectionNotFoundError,
    SetOp,
)
from ontoloom.utils import dquoted


class _Kind(StrEnum):
    """Module-private result kind of a SetExpr evaluation."""

    AXIOMS = "axioms"
    ENTITIES = "entities"


def create_axiom_selection(
    s: Session, name: AxiomSelectionName, expr: SetExpr, *, source: str = ""
) -> AxiomUpsertResult:
    """Create an axiom selection by evaluating a SetExpr tree.

    Raises `SelectionExprError` if `expr` evaluates to entities, not axioms.
    """
    items, kind = _eval_expr(s, expr)
    if kind is not _Kind.AXIOMS:
        msg = f"`{name}` expects an axiom expression; got {kind}."
        raise SelectionExprError(msg)

    auto_source = source or str(expr)
    return upsert_axiom_selection(s, name.bare, items, auto_source)


def create_entity_selection(
    s: Session, name: EntitySelectionName, expr: SetExpr, *, source: str = ""
) -> EntityUpsertResult:
    """Create an entity selection by evaluating a SetExpr tree.

    Raises `SelectionExprError` if `expr` evaluates to axioms, not entities.
    """
    items, kind = _eval_expr(s, expr)
    if kind is not _Kind.ENTITIES:
        msg = f"`{name}` expects an entity expression; got {kind}."
        raise SelectionExprError(msg)

    auto_source = source or str(expr)
    return upsert_entity_selection(s, name.bare, items, auto_source)


def _eval_expr(s: Session, expr: SetOperand) -> tuple[Sequence[str], _Kind]:  # noqa: C901
    if isinstance(expr, str):
        bare = SelectionName(expr)

        if axiom_selection_exists(s, bare):
            return get_axiom_selection_items(s, bare), _Kind.AXIOMS
        if entity_selection_exists(s, bare):
            return get_entity_selection_items(s, bare), _Kind.ENTITIES

        raise SelectionNotFoundError(bare)

    if isinstance(expr, UnionExpr):
        return _eval_set_op(s, expr.union, SetOp.UNION)
    if isinstance(expr, IntersectExpr):
        return _eval_set_op(s, expr.intersect, SetOp.INTERSECTION)
    if isinstance(expr, DiffExpr):
        return _eval_set_op(s, expr.diff, SetOp.DIFFERENCE)

    if isinstance(expr, AxiomsForExpr):
        items, kind = _eval_expr(s, expr.axioms_for)
        if kind is not _Kind.ENTITIES:
            msg = f"`axioms_for` requires an entity expression; operand is {kind}."
            raise SelectionExprError(msg)
        return _axioms_for(s, items), _Kind.AXIOMS

    if isinstance(expr, EntitiesInExpr):
        items, kind = _eval_expr(s, expr.entities_in)
        if kind is not _Kind.AXIOMS:
            msg = f"`entities_in` requires an axiom expression; operand is {kind}."
            raise SelectionExprError(msg)
        return _entities_in(s, items, expr.position), _Kind.ENTITIES

    msg = f"Unknown SetExpr variant: {type(expr).__name__}"
    raise ValueError(msg)


def _eval_set_op(
    s: Session, operands: Sequence[SetOperand], op: SetOp
) -> tuple[Sequence[str], _Kind]:
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
