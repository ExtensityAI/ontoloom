"""Helper functions for ontology operation validation and reference management."""

from ontology_hydra.ontology.models import (
    ClassExpression,
    ClassName,
    IntersectionOf,
    Ontology,
)

# -----------------------------------------------------------------------------
# Validation helpers
# -----------------------------------------------------------------------------


def get_classes_in_expression(expr: ClassExpression):
    """Extract all class names referenced in an expression."""
    if isinstance(expr, IntersectionOf):
        return set(expr.classes)
    return {expr}


def get_classes_in_expressions(exprs: list[ClassExpression]):
    """Extract all class names referenced in a list of expressions."""
    result: set[ClassName] = set()
    for expr in exprs:
        result.update(get_classes_in_expression(expr))
    return result


def remove_class_from_expression(expr: ClassExpression, class_name: ClassName):
    """Remove class from expression. Returns None if expression becomes empty."""
    if isinstance(expr, IntersectionOf):
        remaining = [c for c in expr.classes if c != class_name]
        if not remaining:
            return None
        return IntersectionOf(classes=remaining)
    return None if expr == class_name else expr


def remove_class_from_expressions(exprs: list[ClassExpression], class_name: ClassName):
    """Remove class from all expressions. Returns None if result would be empty."""
    result = []
    for expr in exprs:
        cleaned = remove_class_from_expression(expr, class_name)
        if cleaned is not None:
            result.append(cleaned)
    return result if result else None


def has_cycle(ontology: Ontology, start: ClassName) -> bool:
    """Check if class hierarchy has a cycle starting from start (DFS)."""
    visited: set[ClassName] = set()
    stack = list(ontology.classes[start].sub_class_of) if start in ontology.classes else []

    while stack:
        current = stack.pop()
        if current == start:
            return True
        if current in visited:
            continue
        visited.add(current)
        if current in ontology.classes:
            stack.extend(ontology.classes[current].sub_class_of)

    return False


def validate_classes_exist(ontology: Ontology, class_names: set[ClassName], context: str):
    """Validate that all class names exist in the ontology."""
    for cls in class_names:
        if cls not in ontology.classes:
            msg = f"{context}: class '{cls}' does not exist"
            raise ValueError(msg)


# -----------------------------------------------------------------------------
# Reference replacement helpers
# -----------------------------------------------------------------------------


def replace_class_in_expression(expr: ClassExpression, old_name: ClassName, new_name: ClassName):
    """Replace occurrences of old_name with new_name in a class expression."""
    if isinstance(expr, IntersectionOf):
        return IntersectionOf(classes=[new_name if c == old_name else c for c in expr.classes])
    return new_name if expr == old_name else expr


def replace_class_in_expressions(
    exprs: list[ClassExpression], old_name: ClassName, new_name: ClassName
):
    return [replace_class_in_expression(x, old_name, new_name) for x in exprs]


def replace_class_refs(ontology: Ontology, old_name: ClassName, new_name: ClassName):
    """Replace all references to old_name with new_name throughout the ontology."""
    for cls in ontology.classes.values():
        cls.sub_class_of = [new_name if c == old_name else c for c in cls.sub_class_of]

    for prop in ontology.data_properties.values():
        prop.domain = replace_class_in_expressions(prop.domain, old_name, new_name)

    for prop in ontology.object_properties.values():
        prop.domain = replace_class_in_expressions(prop.domain, old_name, new_name)
        prop.range = replace_class_in_expressions(prop.range, old_name, new_name)
