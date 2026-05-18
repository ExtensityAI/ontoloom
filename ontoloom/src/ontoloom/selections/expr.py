"""Set expressions over selections.

`SetExpr` is the top-level compound-expression type. Its recursive operand
fields hold `SetOperand`, which also accepts a bare `SelectionName` leaf.

Examples:
    {"union": ["sel_a", "sel_b"]}
    {"intersect": ["sel_a", "sel_b"]}
    {"diff": ["sel_a", "sel_b"]}
    {"axioms_for": "ents"}
    {"axioms_for": {"union": ["ents_a", "ents_b"]}}
    {"entities_in": "axs", "position": "sub_class"}
"""

from typing import Annotated, Any, override

from ontoloom.models import FrozenModel, make_tag_resolver, tagged, tagged_union_meta
from ontoloom.owl.markers import Position
from ontoloom.selections.types import SelectionName


class UnionExpr(FrozenModel):
    union: tuple["SetOperand", ...]

    @override
    def __str__(self):
        return "union(" + ", ".join(str(o) for o in self.union) + ")"


class IntersectExpr(FrozenModel):
    intersect: tuple["SetOperand", ...]

    @override
    def __str__(self):
        return "intersect(" + ", ".join(str(o) for o in self.intersect) + ")"


class DiffExpr(FrozenModel):
    """First operand minus all subsequent operands, evaluated left-to-right."""

    diff: tuple["SetOperand", ...]

    @override
    def __str__(self):
        return "diff(" + ", ".join(str(o) for o in self.diff) + ")"


class AxiomsForExpr(FrozenModel):
    axioms_for: "SetOperand"

    @override
    def __str__(self):
        return f"axioms_for({self.axioms_for})"


class EntitiesInExpr(FrozenModel):
    entities_in: "SetOperand"
    position: Position | None = None

    @override
    def __str__(self):
        if self.position is not None:
            return f"entities_in({self.entities_in}, position={self.position})"
        return f"entities_in({self.entities_in})"


_resolve_set_expr = make_tag_resolver(
    (UnionExpr, IntersectExpr, DiffExpr, AxiomsForExpr, EntitiesInExpr),
    union_name="SelectionExpr",
)


def _get_set_operand_tag(v: Any):
    return SelectionName.tag() if isinstance(v, str) else _resolve_set_expr(v)


SetExpr = Annotated[
    (
        tagged(UnionExpr)
        | tagged(IntersectExpr)
        | tagged(DiffExpr)
        | tagged(AxiomsForExpr)
        | tagged(EntitiesInExpr)
    ),
    *tagged_union_meta(_resolve_set_expr),
]

SetOperand = Annotated[
    (
        tagged(SelectionName)
        | tagged(UnionExpr)
        | tagged(IntersectExpr)
        | tagged(DiffExpr)
        | tagged(AxiomsForExpr)
        | tagged(EntitiesInExpr)
    ),
    *tagged_union_meta(_get_set_operand_tag, schema_type=("string", "object")),
]


UnionExpr.model_rebuild()
IntersectExpr.model_rebuild()
DiffExpr.model_rebuild()
AxiomsForExpr.model_rebuild()
EntitiesInExpr.model_rebuild()
