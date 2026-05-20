"""Single renderer for OWL structs.

Replaces 36 near-identical per-class `__str__` overrides across axioms.py and
expressions.py. Format: `ClassName(field, field, ...)` walking `model_fields`
in declaration order. Fields named `annotations` or `negated` are skipped —
they aren't part of the human-facing logical content.

Tuple-valued fields render as `[a, b, c]` when the struct has other fields
alongside (e.g. `HasKey`, `SubObjectPropertyOfChain`); when the tuple is the
struct's only renderable content (e.g. `EquivalentClasses`), it flattens into
the argument list as `a, b, c` without brackets.
"""

from pydantic import BaseModel

from ontoloom.owl.markers import SKIP


def format_owl_struct(obj: BaseModel) -> str:
    fields = [name for name in type(obj).model_fields if name not in SKIP]
    values = [getattr(obj, name) for name in fields]
    only_tuple = len(values) == 1 and isinstance(values[0], tuple)

    if only_tuple:
        parts = [str(v) for v in values[0]]
    else:
        parts = [
            f"[{', '.join(str(v) for v in val)}]" if isinstance(val, tuple) else str(val)
            for val in values
        ]
    return f"{type(obj).__name__}({', '.join(parts)})"
