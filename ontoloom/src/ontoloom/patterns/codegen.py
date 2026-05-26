"""Regenerate the AUTOGEN section of ontoloom/patterns/types.py.

Walks model_fields of every expression and axiom class, reads type annotations
via get_type_hints (preserves alias identity), and emits the parallel pattern
hierarchy by substituting IRI->Slot, ClassExpression->ExprSlot, DataRange->DataRange|Slot,
and appending |Contains to Unordered tuple fields.

Only the portion of types.py below the AUTOGEN marker is rewritten — the
hand-written header (imports + BasePattern) is preserved.

Run: uv run ontoloom-gen-patterns
"""

import subprocess
import sys
import types
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, get_args, get_origin

from ontoloom.owl.axioms import AXIOM_CLASSES
from ontoloom.owl.expressions import ClassExpression
from ontoloom.owl.iri import IRI
from ontoloom.owl.literals import DataRange
from ontoloom.owl.markers import SKIP, is_unordered

_TARGET = Path(__file__).parent / "types.py"
_MARKER = "# ---- AUTOGEN BELOW: do not edit; regenerate via `uv run ontoloom-gen-patterns` ----"


def _peel_union_member(member: object) -> type | None:
    """Strip Annotated[X, Tag(...)] to X; skip IRI (no pattern class needed)."""
    if get_origin(member) is Annotated:
        inner = get_args(member)[0]
        return None if inner is IRI else inner
    return member if isinstance(member, type) else None


_EXPR_CLASSES: tuple[type, ...] = tuple(
    m
    for raw in get_args(get_args(ClassExpression)[0])
    if (m := _peel_union_member(raw)) is not None
)
_PATTERN_CLASSES: frozenset[type] = frozenset(_EXPR_CLASSES) | frozenset(AXIOM_CLASSES)

# The raw ClassExpression union (without the Annotated wrapper).
# Annotated[ClassExpression, marker] flattens nested Annotated to
# Annotated[_EXPR_UNION, Field(...), marker], so we detect ExprSlot fields
# by checking whether the first Annotated arg IS this union, not the alias.
_EXPR_UNION = get_args(ClassExpression)[0]
# Same trick for DataRange: it's `Annotated[DataTypeRef | DataIntersectionOf | DataOneOf, ...]`
# and we want to detect the inner union, not the alias.
_DATA_RANGE_UNION = get_args(DataRange)[0]


def generate_body():
    """Emit the AUTOGEN section content (everything below the marker)."""
    lines: list[str] = []
    needs_rebuild: list[str] = []

    for cls in _EXPR_CLASSES:
        emitted = _emit_class(cls)
        lines.extend(emitted.lines)
        lines.append("")
        if emitted.needs_rebuild:
            needs_rebuild.append(cls.__name__ + "Pattern")

    lines.append(f"ExprSlot = Slot | {' | '.join(c.__name__ + 'Pattern' for c in _EXPR_CLASSES)}")
    lines.append("")

    for cls in AXIOM_CLASSES:
        emitted = _emit_class(cls)
        lines.extend(emitted.lines)
        lines.append("")
        if emitted.needs_rebuild:
            needs_rebuild.append(cls.__name__ + "Pattern")

    expr_names = " | ".join(c.__name__ + "Pattern" for c in _EXPR_CLASSES)
    axiom_names = " | ".join(c.__name__ + "Pattern" for c in AXIOM_CLASSES)
    all_pattern_classes = [c.__name__ + "Pattern" for c in (*_EXPR_CLASSES, *AXIOM_CLASSES)]
    tagged_union = " | ".join(f'Annotated[{n}, Tag("{n}")]' for n in all_pattern_classes)
    lines += [
        f"ExpressionPattern = {expr_names}",
        f"AxiomPattern = {axiom_names}",
        "_PATTERN_CLASSES = (",
        *(f"    {n}," for n in all_pattern_classes),
        ")",
        '_get_pattern_tag = make_tag_resolver(_PATTERN_CLASSES, union_name="Pattern")',
        f"Pattern = Annotated[{tagged_union}, *tagged_union_meta(_get_pattern_tag)]",
        "",
    ]
    lines.extend(f"{name}.model_rebuild()" for name in needs_rebuild)

    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class EmittedClass:
    lines: tuple[str, ...]
    needs_rebuild: bool


def _emit_class(cls: type):
    pattern_name = cls.__name__ + "Pattern"
    lines: list[str] = [f"class {pattern_name}(BasePattern):"]
    needs_rebuild = False
    hints = typing.get_type_hints(cls, include_extras=True)
    for field_name, info in cls.model_fields.items():
        if field_name in SKIP:
            continue
        unordered = is_unordered(info)
        field_type = _to_pattern_type(hints[field_name], unordered)
        lines.append(f"    {field_name}: {field_type}")
        if "ExprSlot" in field_type:
            needs_rebuild = True
        # Sibling enum for unordered tuple fields -> matcher reads it to pick
        # between exact set-equality and subset. See TupleMatch docstring.
        if unordered:
            lines.append(f"    {field_name}_match: TupleMatch = TupleMatch.EXACT")

    return EmittedClass(lines=tuple(lines), needs_rebuild=needs_rebuild)


def _leaf_pattern(t: object) -> str | None:
    """Pattern type for a type that has no further structure to recurse into.
    Returns None for composites (Annotated, tuple, union) -> caller dispatches."""
    if t is IRI:
        return "Slot"
    if t is _EXPR_UNION:
        return "ExprSlot"
    if t is _DATA_RANGE_UNION:
        return "DataRange | Slot"
    if isinstance(t, type) and t in _PATTERN_CLASSES:
        return t.__name__ + "Pattern"
    return None


def _to_pattern_type(t: object, unordered: bool = False) -> str:
    if get_origin(t) is Annotated:
        # Annotated[ClassExpression, marker] flattens to Annotated[_EXPR_UNION, Field, marker]
        # so we must detect leaves here before stripping, not after.
        leaf = _leaf_pattern(get_args(t)[0])
        return leaf if leaf is not None else _to_pattern_type(get_args(t)[0], unordered)

    leaf = _leaf_pattern(t)
    if leaf is not None:
        return leaf

    origin = get_origin(t)
    if origin is tuple:
        inner = _to_pattern_type(get_args(t)[0])
        return f"tuple[{inner}, ...]"

    if origin is types.UnionType or origin is typing.Union:
        parts = [_union_member(arg) for arg in get_args(t)]
        if "Slot" not in parts:
            parts.append("Slot")
        return " | ".join(parts)

    name = getattr(t, "__name__", None)
    return f"{name} | Slot" if name else repr(t)


def _union_member(t: object) -> str:
    """Render a type that appears inside a union. IRI is kept as IRI (not collapsed to Slot)."""
    if t is IRI:
        return "IRI"
    if t is _EXPR_UNION:
        return "ExprSlot"
    if t is _DATA_RANGE_UNION:
        return "DataRange"
    if isinstance(t, type) and t in _PATTERN_CLASSES:
        return t.__name__ + "Pattern"
    if get_origin(t) is Annotated:
        args = get_args(t)
        if args[0] is _EXPR_UNION:
            return "ExprSlot"
        if args[0] is _DATA_RANGE_UNION:
            return "DataRange"
        return _union_member(args[0])
    return getattr(t, "__name__", repr(t))


def _splice(existing: str, body: str) -> str:
    """Replace the AUTOGEN portion of `existing` with `body`."""
    if _MARKER not in existing:
        msg = f"AUTOGEN marker not found in {_TARGET}; cannot splice."
        raise RuntimeError(msg)
    head, _, _tail = existing.partition(_MARKER)
    return head + _MARKER + "\n\n" + body


def _ruff_format_text(text: str) -> str:
    """Run ruff format on `text` as if it were _TARGET; return the formatted output."""
    result = subprocess.run(
        ["ruff", "format", "--stdin-filename", str(_TARGET), "-"],
        input=text,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def main() -> None:
    body = generate_body()
    existing = _TARGET.read_text()
    new_text = _ruff_format_text(_splice(existing, body))
    if "--check" in sys.argv:
        if existing != new_text:
            sys.stderr.write(
                "patterns/types.py AUTOGEN section is out of sync. "
                "Run: uv run ontoloom-gen-patterns\n"
            )
            sys.exit(1)
    else:
        _TARGET.write_text(new_text)
        print(f"Wrote {_TARGET}")  # noqa: T201


if __name__ == "__main__":
    main()
