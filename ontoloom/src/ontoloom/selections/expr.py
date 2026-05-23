"""Set expressions over selections, split by result kind.

Two parallel typed hierarchies replace the previous single `SetExpr` whose
leaves were bare names: `AxiomSetExpr` produces axiom hashes, `EntitySetExpr`
produces entity IRIs. Leaves carry kind via `AxiomSelectionName` /
`EntitySelectionName` (kind-prefixed on the wire, e.g. `"axioms:foo"` /
`"entities:bar"`). Cross-kind conversion lives on `AxiomsForExpr` (entities ->
axioms) and `EntitiesInExpr` (axioms -> entities).

Examples:
    AxiomSetExpr
        "axioms:foo"
        {"union": ["axioms:a", "axioms:b"]}
        {"axioms_for": "entities:ents"}
        {"axioms_for": {"union": ["entities:a", "entities:b"]}}
    EntitySetExpr
        "entities:bar"
        {"intersect": ["entities:a", "entities:b"]}
        {"entities_in": "axioms:axs", "position": "sub_class"}
"""

from typing import Annotated, Any, override

from typing_extensions import TypeIs

from ontoloom.models import FrozenModel, make_tag_resolver, tagged, tagged_union_meta
from ontoloom.owl.markers import Position
from ontoloom.selections.types import AxiomSelectionName, EntitySelectionName

# -- Axiom-producing expressions --


class AxiomUnionExpr(FrozenModel):
    union: tuple["AxiomSetExpr", ...]

    @override
    def __str__(self):
        return "union(" + ", ".join(str(o) for o in self.union) + ")"


class AxiomIntersectExpr(FrozenModel):
    intersect: tuple["AxiomSetExpr", ...]

    @override
    def __str__(self):
        return "intersect(" + ", ".join(str(o) for o in self.intersect) + ")"


class AxiomDiffExpr(FrozenModel):
    """First operand minus all subsequent operands, evaluated left-to-right."""

    diff: tuple["AxiomSetExpr", ...]

    @override
    def __str__(self):
        return "diff(" + ", ".join(str(o) for o in self.diff) + ")"


class AxiomsForExpr(FrozenModel):
    """Cross-kind: axioms mentioning any entity in the operand expression."""

    axioms_for: "EntitySetExpr"

    @override
    def __str__(self):
        return f"axioms_for({self.axioms_for})"


# -- Entity-producing expressions --


class EntityUnionExpr(FrozenModel):
    union: tuple["EntitySetExpr", ...]

    @override
    def __str__(self):
        return "union(" + ", ".join(str(o) for o in self.union) + ")"


class EntityIntersectExpr(FrozenModel):
    intersect: tuple["EntitySetExpr", ...]

    @override
    def __str__(self):
        return "intersect(" + ", ".join(str(o) for o in self.intersect) + ")"


class EntityDiffExpr(FrozenModel):
    """First operand minus all subsequent operands, evaluated left-to-right."""

    diff: tuple["EntitySetExpr", ...]

    @override
    def __str__(self):
        return "diff(" + ", ".join(str(o) for o in self.diff) + ")"


class EntitiesInExpr(FrozenModel):
    """Cross-kind: entities mentioned by axioms in the operand expression,
    optionally restricted to a structural slot."""

    entities_in: "AxiomSetExpr"
    position: Position | None = None

    @override
    def __str__(self):
        if self.position is not None:
            return f"entities_in({self.entities_in}, position={self.position})"
        return f"entities_in({self.entities_in})"


# -- Discriminated unions --

_resolve_axiom_expr = make_tag_resolver(
    (AxiomUnionExpr, AxiomIntersectExpr, AxiomDiffExpr, AxiomsForExpr),
    union_name="AxiomSetExpr",
)

_resolve_entity_expr = make_tag_resolver(
    (EntityUnionExpr, EntityIntersectExpr, EntityDiffExpr, EntitiesInExpr),
    union_name="EntitySetExpr",
)


def _get_axiom_set_expr_tag(v: Any):
    return AxiomSelectionName.tag() if isinstance(v, str) else _resolve_axiom_expr(v)


def _get_entity_set_expr_tag(v: Any):
    return EntitySelectionName.tag() if isinstance(v, str) else _resolve_entity_expr(v)


AxiomSetExpr = Annotated[
    (
        tagged(AxiomSelectionName)
        | tagged(AxiomUnionExpr)
        | tagged(AxiomIntersectExpr)
        | tagged(AxiomDiffExpr)
        | tagged(AxiomsForExpr)
    ),
    *tagged_union_meta(_get_axiom_set_expr_tag, schema_type=("string", "object")),
]

EntitySetExpr = Annotated[
    (
        tagged(EntitySelectionName)
        | tagged(EntityUnionExpr)
        | tagged(EntityIntersectExpr)
        | tagged(EntityDiffExpr)
        | tagged(EntitiesInExpr)
    ),
    *tagged_union_meta(_get_entity_set_expr_tag, schema_type=("string", "object")),
]


# Runtime-checkable tuples of concrete classes for each side. Use the typed
# `is_axiom_set_expr` / `is_entity_set_expr` predicates at boundary layers
# (MCP tool dispatch) to route a parsed expression to the right typed walker —
# they narrow `AxiomSetExpr | EntitySetExpr` to the matching arm.
_AXIOM_SET_EXPR_TYPES: tuple[type, ...] = (
    AxiomSelectionName,
    AxiomUnionExpr,
    AxiomIntersectExpr,
    AxiomDiffExpr,
    AxiomsForExpr,
)

_ENTITY_SET_EXPR_TYPES: tuple[type, ...] = (
    EntitySelectionName,
    EntityUnionExpr,
    EntityIntersectExpr,
    EntityDiffExpr,
    EntitiesInExpr,
)


def is_axiom_set_expr(value: "AxiomSetExpr | EntitySetExpr") -> TypeIs["AxiomSetExpr"]:
    return isinstance(value, _AXIOM_SET_EXPR_TYPES)


def is_entity_set_expr(value: "AxiomSetExpr | EntitySetExpr") -> TypeIs["EntitySetExpr"]:
    return isinstance(value, _ENTITY_SET_EXPR_TYPES)


AxiomUnionExpr.model_rebuild()
AxiomIntersectExpr.model_rebuild()
AxiomDiffExpr.model_rebuild()
AxiomsForExpr.model_rebuild()
EntityUnionExpr.model_rebuild()
EntityIntersectExpr.model_rebuild()
EntityDiffExpr.model_rebuild()
EntitiesInExpr.model_rebuild()
