"""Evaluate `SetExpr` trees to `(kind, items)` and persist the result."""

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
from ontoloom.query.dispatch import execute
from ontoloom.query.find_axioms import FindAxioms
from ontoloom.query.find_entities import FindEntities
from ontoloom.selections.expr import (
    AxiomsForExpr,
    DiffExpr,
    EntitiesInExpr,
    IntersectExpr,
    SetExpr,
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
    SelectionExprError,
    SelectionKind,
    SelectionName,
    SelectionNotFoundError,
    SetOp,
    WriteMode,
)
from ontoloom.utils import difference_ordered, dquoted, intersect_ordered, union_ordered


def create_selection_from_expr(
    s: Session,
    name: SelectionName,
    expr: SetExpr,
    *,
    mode: WriteMode = WriteMode.CREATE,
) -> AxiomUpsertResult | EntityUpsertResult:
    """Evaluate a set-expr and persist the result under `name`, kind inferred from the expr."""
    kind, items = evaluate_set_expr(s, expr)
    auto_source = str(expr)

    if kind is SelectionKind.AXIOMS:
        return upsert_axiom_selection(
            s, name, [AxiomHash(i) for i in items], auto_source, mode=mode
        )

    return upsert_entity_selection(s, name, [IRI(i) for i in items], auto_source, mode=mode)


def evaluate_set_expr(s: Session, expr: SetExpr) -> tuple[SelectionKind, list[str]]:  # noqa: C901
    match expr:
        case SelectionName():
            if axiom_selection_exists(s, expr):
                return SelectionKind.AXIOMS, list(get_axiom_selection_items(s, expr))

            if entity_selection_exists(s, expr):
                return SelectionKind.ENTITIES, list(get_entity_selection_items(s, expr))

            raise SelectionNotFoundError(expr)
        case UnionExpr():
            return _combine(s, expr.union, SetOp.UNION)
        case IntersectExpr():
            return _combine(s, expr.intersect, SetOp.INTERSECTION)
        case DiffExpr():
            return _combine(s, expr.diff, SetOp.DIFFERENCE)
        case AxiomsForExpr():
            kind, items = evaluate_set_expr(s, expr.axioms_for)

            if kind is not SelectionKind.ENTITIES:
                msg = "axioms_for requires an entity-producing operand."
                raise SelectionExprError(msg)

            return SelectionKind.AXIOMS, list(find_axioms_for(s, [IRI(i) for i in items]))
        case EntitiesInExpr():
            kind, items = evaluate_set_expr(s, expr.entities_in)

            if kind is not SelectionKind.AXIOMS:
                msg = "entities_in requires an axiom-producing operand."
                raise SelectionExprError(msg)

            return SelectionKind.ENTITIES, list(
                find_entities_in(s, [AxiomHash(i) for i in items], expr.position)
            )
        case _:
            msg = f"Unknown SetExpr variant: {type(expr).__name__}"
            raise ValueError(msg)


def _combine(s: Session, operands: Sequence[SetExpr], op: SetOp) -> tuple[SelectionKind, list[str]]:
    _check_arity(op, len(operands))
    evaluated = [evaluate_set_expr(s, sub) for sub in operands]
    kinds = {kind for kind, _ in evaluated}

    if len(kinds) > 1:
        msg = "set operations require all operands to be the same kind (axioms or entities)."
        raise SelectionExprError(msg)

    results = [items for _, items in evaluated]
    return next(iter(kinds)), _apply_set_op(results, op)


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


def find_axioms_for(s: Session, entity_iris: Sequence[IRI]) -> list[AxiomHash]:
    if not entity_iris:
        return []

    return execute(s, FindAxioms(constraints=(MentionsAny(iris=tuple(entity_iris)),)))


def find_entities_in(
    s: Session, axiom_hashes: Sequence[AxiomHash], field: Position | None
) -> list[IRI]:
    if not axiom_hashes:
        return []

    constraints: list[EntityConstraint] = [MentionedIn(hashes=tuple(axiom_hashes))]

    if field is not None:
        constraints.append(InPositions(positions=(field,)))

    return execute(s, FindEntities(constraints=tuple(constraints)))
