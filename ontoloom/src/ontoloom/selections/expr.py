"""Set expressions over selections — a single kind-agnostic grammar.

Leaves are bare selection names (`SelectionName`); kind is resolved during
evaluation (`compose.eval_set_expr`), not encoded in the wire form. Set ops
(`union`/`intersect`/`diff`) require all operands to resolve to the same kind;
the cross-kind operators `axioms_for` (entities -> axioms) and `entities_in`
(axioms -> entities) flip kind.

Examples:
    "foo"
    {"union": ["a", "b"]}
    {"axioms_for": "ents"}
    {"entities_in": "axs", "position": "sub_class"}
"""

from typing import Annotated, Any, override

from ontoloom.models import FrozenModel, make_tag_resolver, tagged, tagged_union_meta
from ontoloom.owl.markers import Position
from ontoloom.selections.types import SelectionName


class UnionExpr(FrozenModel):
    union: tuple["SetExpr", ...]

    @override
    def __str__(self):
        return "union(" + ", ".join(str(o) for o in self.union) + ")"


class IntersectExpr(FrozenModel):
    intersect: tuple["SetExpr", ...]

    @override
    def __str__(self):
        return "intersect(" + ", ".join(str(o) for o in self.intersect) + ")"


class DiffExpr(FrozenModel):
    """First operand minus all subsequent operands, evaluated left-to-right."""

    diff: tuple["SetExpr", ...]

    @override
    def __str__(self):
        return "diff(" + ", ".join(str(o) for o in self.diff) + ")"


class AxiomsForExpr(FrozenModel):
    """Cross-kind: axioms mentioning any entity in the operand (operand must eval to entities)."""

    axioms_for: "SetExpr"

    @override
    def __str__(self):
        return f"axioms_for({self.axioms_for})"


class EntitiesInExpr(FrozenModel):
    """Cross-kind: entities mentioned by axioms in the operand (operand must eval to axioms),
    optionally restricted to a structural slot."""

    entities_in: "SetExpr"
    position: Position | None = None

    @override
    def __str__(self):
        if self.position is not None:
            return f"entities_in({self.entities_in}, position={self.position})"

        return f"entities_in({self.entities_in})"


_resolve_set_expr = make_tag_resolver(
    (UnionExpr, IntersectExpr, DiffExpr, AxiomsForExpr, EntitiesInExpr),
    union_name="SetExpr",
)


def _get_set_expr_tag(v: Any):
    return SelectionName.tag() if isinstance(v, str) else _resolve_set_expr(v)


SetExpr = Annotated[
    (
        tagged(SelectionName)
        | tagged(UnionExpr)
        | tagged(IntersectExpr)
        | tagged(DiffExpr)
        | tagged(AxiomsForExpr)
        | tagged(EntitiesInExpr)
    ),
    *tagged_union_meta(_get_set_expr_tag, schema_type=("string", "object")),
]


UnionExpr.model_rebuild()
IntersectExpr.model_rebuild()
DiffExpr.model_rebuild()
AxiomsForExpr.model_rebuild()
EntitiesInExpr.model_rebuild()
