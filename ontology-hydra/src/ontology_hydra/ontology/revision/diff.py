"""Semantic diff tool for comparing ontologies."""

from collections.abc import Callable
from enum import StrEnum
from typing import Any, Literal

from ontology_hydra.ontology.models import (
    Class,
    ClassExpression,
    ClassName,
    DataProperty,
    IntersectionOf,
    ObjectProperty,
    Ontology,
    PropertyName,
)
from ontology_hydra.utils.schema.llm import DataModel

# -----------------------------------------------------------------------------
# Diff data models
# -----------------------------------------------------------------------------


class Action(StrEnum):
    added = "added"
    removed = "removed"
    modified = "modified"


class ClassAdded(DataModel):
    action: Literal[Action.added] = Action.added
    cls: Class


class ClassModified(DataModel):
    action: Literal[Action.modified] = Action.modified
    name: ClassName
    old: Class
    new: Class


class ClassRemoved(DataModel):
    action: Literal[Action.removed] = Action.removed
    name: ClassName


class DataPropertyAdded(DataModel):
    action: Literal[Action.added] = Action.added
    prop: DataProperty


class DataPropertyModified(DataModel):
    action: Literal[Action.modified] = Action.modified
    name: PropertyName
    old: DataProperty
    new: DataProperty


class DataPropertyRemoved(DataModel):
    action: Literal[Action.removed] = Action.removed
    name: PropertyName


class ObjectPropertyAdded(DataModel):
    action: Literal[Action.added] = Action.added
    prop: ObjectProperty


class ObjectPropertyModified(DataModel):
    action: Literal[Action.modified] = Action.modified
    name: PropertyName
    old: ObjectProperty
    new: ObjectProperty


class ObjectPropertyRemoved(DataModel):
    action: Literal[Action.removed] = Action.removed
    name: PropertyName


ClassChange = ClassAdded | ClassRemoved | ClassModified
DataPropertyChange = DataPropertyAdded | DataPropertyRemoved | DataPropertyModified
ObjectPropertyChange = ObjectPropertyAdded | ObjectPropertyRemoved | ObjectPropertyModified


class OntologyDiff(DataModel):
    classes: list[ClassChange]
    data_properties: list[DataPropertyChange]
    object_properties: list[ObjectPropertyChange]

    @property
    def is_empty(self):
        return not (self.classes or self.data_properties or self.object_properties)


# -----------------------------------------------------------------------------
# Diff computation
# -----------------------------------------------------------------------------


def _diff_dict[K: str, V, Added, Removed, Modified](
    old_dict: dict[K, V],
    new_dict: dict[K, V],
    make_added: Callable[[V], Added],
    make_removed: Callable[[K], Removed],
    make_modified: Callable[[K, V, V], Modified],
):
    """Generic diff for two dicts: returns added, removed, and modified items."""

    changes = list[Added | Removed | Modified]()
    old_keys, new_keys = set(old_dict.keys()), set(new_dict.keys())

    for key in sorted(new_keys - old_keys):
        changes.append(make_added(new_dict[key]))
    for key in sorted(old_keys - new_keys):
        changes.append(make_removed(key))
    for key in sorted(old_keys & new_keys):
        if old_dict[key] != new_dict[key]:
            changes.append(make_modified(key, old_dict[key], new_dict[key]))

    return changes


def diff_ontology(old: Ontology, new: Ontology):
    """Compute the semantic diff between two ontologies."""
    return OntologyDiff(
        classes=_diff_dict(
            old.classes,
            new.classes,
            lambda v: ClassAdded(cls=v),
            lambda k: ClassRemoved(name=k),
            lambda k, o, n: ClassModified(name=k, old=o, new=n),
        ),
        data_properties=_diff_dict(
            old.data_properties,
            new.data_properties,
            lambda v: DataPropertyAdded(prop=v),
            lambda k: DataPropertyRemoved(name=k),
            lambda k, o, n: DataPropertyModified(name=k, old=o, new=n),
        ),
        object_properties=_diff_dict(
            old.object_properties,
            new.object_properties,
            lambda v: ObjectPropertyAdded(prop=v),
            lambda k: ObjectPropertyRemoved(name=k),
            lambda k, o, n: ObjectPropertyModified(name=k, old=o, new=n),
        ),
    )


# -----------------------------------------------------------------------------
# Formatting
# -----------------------------------------------------------------------------


def _format_expr(expr: ClassExpression):
    """Format a class expression for display."""
    if isinstance(expr, IntersectionOf):
        return f"({' & '.join(expr.classes)})"
    return str(expr)


def _format_exprs(exprs: list[ClassExpression]):
    """Format a list of class expressions for display."""
    if not exprs:
        return "[]"
    return "[" + ", ".join(_format_expr(e) for e in exprs) + "]"


def _field_change(label: str, old_val: Any, new_val: Any, quote: bool = False):
    """Return a formatted field change line if values differ, else None."""
    if old_val == new_val:
        return None
    if quote:
        return f'      {label}: "{old_val}" -> "{new_val}"'
    return f"      {label}: {old_val} -> {new_val}"


def _description_changes(old, new):
    """Return formatted lines for definition/constraints changes."""
    lines = list[str]()
    if line := _field_change(
        "definition", old.description.definition, new.description.definition, quote=True
    ):
        lines.append(line)

    if line := _field_change(
        "constraints", old.description.constraints, new.description.constraints, quote=True
    ):
        lines.append(line)
    return lines


def _format_class_change(change: ClassChange):
    """Format a single class change."""
    if isinstance(change, ClassAdded):
        lines = [f'  + {change.cls.name}: "{change.cls.description.definition}"']
        if change.cls.sub_class_of:
            lines.append(f"      sub_class_of: {change.cls.sub_class_of}")
        return lines

    if isinstance(change, ClassRemoved):
        return [f"  - {change.name}"]

    # ClassModified
    lines = [f"  ~ {change.name}:"]
    lines.extend(_description_changes(change.old, change.new))
    if line := _field_change("sub_class_of", change.old.sub_class_of, change.new.sub_class_of):
        lines.append(line)
    return lines


def _format_data_property_change(change: DataPropertyChange):
    """Format a single data property change."""
    if isinstance(change, DataPropertyAdded):
        return [
            f'  + {change.prop.name}: "{change.prop.description.definition}"',
            f"      domain: {_format_exprs(change.prop.domain)}, range: {change.prop.range}",
        ]

    if isinstance(change, DataPropertyRemoved):
        return [f"  - {change.name}"]

    # DataPropertyModified
    lines = [f"  ~ {change.name}:"]
    lines.extend(_description_changes(change.old, change.new))
    if line := _field_change(
        "domain", _format_exprs(change.old.domain), _format_exprs(change.new.domain)
    ):
        lines.append(line)
    if line := _field_change("range", change.old.range, change.new.range):
        lines.append(line)
    return lines


def _format_object_property_change(change: ObjectPropertyChange):
    """Format a single object property change."""
    if isinstance(change, ObjectPropertyAdded):
        return [
            f'  + {change.prop.name}: "{change.prop.description.definition}"',
            f"      domain: {_format_exprs(change.prop.domain)}, range: {_format_exprs(change.prop.range)}",
        ]

    if isinstance(change, ObjectPropertyRemoved):
        return [f"  - {change.name}"]

    # ObjectPropertyModified
    lines = [f"  ~ {change.name}:"]
    lines.extend(_description_changes(change.old, change.new))
    if line := _field_change(
        "domain", _format_exprs(change.old.domain), _format_exprs(change.new.domain)
    ):
        lines.append(line)
    if line := _field_change(
        "range", _format_exprs(change.old.range), _format_exprs(change.new.range)
    ):
        lines.append(line)
    return lines


def _format_section[C](
    title: str, changes: list[C], formatter: Callable[[C], list[str]]
) -> str | None:
    """Format a section of changes, returning None if empty."""
    if not changes:
        return None

    lines = list[str]()
    for change in changes:
        lines.extend(formatter(change))
    return f"{title}:\n" + "\n".join(lines)


def format_diff(diff: OntologyDiff) -> str:
    """Format an OntologyDiff as human-readable text."""
    if diff.is_empty:
        return "No changes."

    sections = [
        _format_section("Classes", diff.classes, _format_class_change),
        _format_section("Data Properties", diff.data_properties, _format_data_property_change),
        _format_section(
            "Object Properties", diff.object_properties, _format_object_property_change
        ),
    ]
    return "\n\n".join(s for s in sections if s)
