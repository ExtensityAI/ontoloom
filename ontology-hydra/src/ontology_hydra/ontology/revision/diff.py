"""Semantic diff tool for comparing ontologies."""

from typing import Literal

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


class ClassAdded(DataModel):
    action: Literal["added"] = "added"
    cls: Class


class ClassRemoved(DataModel):
    action: Literal["removed"] = "removed"
    name: ClassName


class ClassModified(DataModel):
    action: Literal["modified"] = "modified"
    name: ClassName
    old: Class
    new: Class


class DataPropertyAdded(DataModel):
    action: Literal["added"] = "added"
    prop: DataProperty


class DataPropertyRemoved(DataModel):
    action: Literal["removed"] = "removed"
    name: PropertyName


class DataPropertyModified(DataModel):
    action: Literal["modified"] = "modified"
    name: PropertyName
    old: DataProperty
    new: DataProperty


class ObjectPropertyAdded(DataModel):
    action: Literal["added"] = "added"
    prop: ObjectProperty


class ObjectPropertyRemoved(DataModel):
    action: Literal["removed"] = "removed"
    name: PropertyName


class ObjectPropertyModified(DataModel):
    action: Literal["modified"] = "modified"
    name: PropertyName
    old: ObjectProperty
    new: ObjectProperty


ClassChange = ClassAdded | ClassRemoved | ClassModified
DataPropertyChange = DataPropertyAdded | DataPropertyRemoved | DataPropertyModified
ObjectPropertyChange = ObjectPropertyAdded | ObjectPropertyRemoved | ObjectPropertyModified


class OntologyDiff(DataModel):
    classes: list[ClassChange]
    data_properties: list[DataPropertyChange]
    object_properties: list[ObjectPropertyChange]

    @property
    def is_empty(self) -> bool:
        return not (self.classes or self.data_properties or self.object_properties)


# -----------------------------------------------------------------------------
# Diff computation
# -----------------------------------------------------------------------------


def diff_ontology(old: Ontology, new: Ontology) -> OntologyDiff:
    """Compute the semantic diff between two ontologies."""
    class_changes: list[ClassChange] = []
    old_classes = set(old.classes.keys())
    new_classes = set(new.classes.keys())

    for name in sorted(new_classes - old_classes):
        class_changes.append(ClassAdded(cls=new.classes[name]))
    for name in sorted(old_classes - new_classes):
        class_changes.append(ClassRemoved(name=name))
    for name in sorted(old_classes & new_classes):
        if old.classes[name] != new.classes[name]:
            class_changes.append(
                ClassModified(name=name, old=old.classes[name], new=new.classes[name])
            )

    data_prop_changes: list[DataPropertyChange] = []
    old_data_props = set(old.data_properties.keys())
    new_data_props = set(new.data_properties.keys())

    for name in sorted(new_data_props - old_data_props):
        data_prop_changes.append(DataPropertyAdded(prop=new.data_properties[name]))
    for name in sorted(old_data_props - new_data_props):
        data_prop_changes.append(DataPropertyRemoved(name=name))
    for name in sorted(old_data_props & new_data_props):
        if old.data_properties[name] != new.data_properties[name]:
            data_prop_changes.append(
                DataPropertyModified(
                    name=name, old=old.data_properties[name], new=new.data_properties[name]
                )
            )

    obj_prop_changes: list[ObjectPropertyChange] = []
    old_obj_props = set(old.object_properties.keys())
    new_obj_props = set(new.object_properties.keys())

    for name in sorted(new_obj_props - old_obj_props):
        obj_prop_changes.append(ObjectPropertyAdded(prop=new.object_properties[name]))
    for name in sorted(old_obj_props - new_obj_props):
        obj_prop_changes.append(ObjectPropertyRemoved(name=name))
    for name in sorted(old_obj_props & new_obj_props):
        if old.object_properties[name] != new.object_properties[name]:
            obj_prop_changes.append(
                ObjectPropertyModified(
                    name=name, old=old.object_properties[name], new=new.object_properties[name]
                )
            )

    return OntologyDiff(
        classes=class_changes,
        data_properties=data_prop_changes,
        object_properties=obj_prop_changes,
    )


# -----------------------------------------------------------------------------
# Formatting
# -----------------------------------------------------------------------------


def _format_expression(expr: ClassExpression) -> str:
    """Format a class expression for display."""
    if isinstance(expr, IntersectionOf):
        return f"({' & '.join(expr.classes)})"
    return expr


def _format_expressions(exprs: list[ClassExpression]) -> str:
    """Format a list of class expressions for display."""
    if not exprs:
        return "[]"
    return "[" + ", ".join(_format_expression(e) for e in exprs) + "]"


def _format_class_change(change: ClassChange) -> list[str]:
    """Format a single class change."""
    lines = []
    if isinstance(change, ClassAdded):
        lines.append(f'  + {change.cls.name}: "{change.cls.description.definition}"')
        if change.cls.sub_class_of:
            lines.append(f"      sub_class_of: {change.cls.sub_class_of}")
    elif isinstance(change, ClassRemoved):
        lines.append(f"  - {change.name}")
    elif isinstance(change, ClassModified):
        lines.append(f"  ~ {change.name}:")
        if change.old.description.definition != change.new.description.definition:
            lines.append(
                f'      definition: "{change.old.description.definition}" -> "{change.new.description.definition}"'
            )
        if change.old.description.constraints != change.new.description.constraints:
            lines.append(
                f'      constraints: "{change.old.description.constraints}" -> "{change.new.description.constraints}"'
            )
        if change.old.sub_class_of != change.new.sub_class_of:
            lines.append(
                f"      sub_class_of: {change.old.sub_class_of} -> {change.new.sub_class_of}"
            )
    return lines


def _format_data_property_change(change: DataPropertyChange) -> list[str]:
    """Format a single data property change."""
    lines = []
    if isinstance(change, DataPropertyAdded):
        lines.append(f'  + {change.prop.name}: "{change.prop.description.definition}"')
        lines.append(
            f"      domain: {_format_expressions(change.prop.domain)}, range: {change.prop.range}"
        )
    elif isinstance(change, DataPropertyRemoved):
        lines.append(f"  - {change.name}")
    elif isinstance(change, DataPropertyModified):
        lines.append(f"  ~ {change.name}:")
        if change.old.description.definition != change.new.description.definition:
            lines.append(
                f'      definition: "{change.old.description.definition}" -> "{change.new.description.definition}"'
            )
        if change.old.description.constraints != change.new.description.constraints:
            lines.append(
                f'      constraints: "{change.old.description.constraints}" -> "{change.new.description.constraints}"'
            )
        if change.old.domain != change.new.domain:
            lines.append(
                f"      domain: {_format_expressions(change.old.domain)} -> {_format_expressions(change.new.domain)}"
            )
        if change.old.range != change.new.range:
            lines.append(f"      range: {change.old.range} -> {change.new.range}")
    return lines


def _format_object_property_change(change: ObjectPropertyChange) -> list[str]:
    """Format a single object property change."""
    lines = []
    if isinstance(change, ObjectPropertyAdded):
        lines.append(f'  + {change.prop.name}: "{change.prop.description.definition}"')
        lines.append(
            f"      domain: {_format_expressions(change.prop.domain)}, range: {_format_expressions(change.prop.range)}"
        )
    elif isinstance(change, ObjectPropertyRemoved):
        lines.append(f"  - {change.name}")
    elif isinstance(change, ObjectPropertyModified):
        lines.append(f"  ~ {change.name}:")
        if change.old.description.definition != change.new.description.definition:
            lines.append(
                f'      definition: "{change.old.description.definition}" -> "{change.new.description.definition}"'
            )
        if change.old.description.constraints != change.new.description.constraints:
            lines.append(
                f'      constraints: "{change.old.description.constraints}" -> "{change.new.description.constraints}"'
            )
        if change.old.domain != change.new.domain:
            lines.append(
                f"      domain: {_format_expressions(change.old.domain)} -> {_format_expressions(change.new.domain)}"
            )
        if change.old.range != change.new.range:
            lines.append(
                f"      range: {_format_expressions(change.old.range)} -> {_format_expressions(change.new.range)}"
            )
    return lines


def format_diff(diff: OntologyDiff) -> str:
    """Format an OntologyDiff as human-readable text."""
    if diff.is_empty:
        return "No changes."

    sections = []

    if diff.classes:
        class_lines = []
        for change in diff.classes:
            class_lines.extend(_format_class_change(change))
        sections.append("Classes:\n" + "\n".join(class_lines))

    if diff.data_properties:
        data_prop_lines = []
        for change in diff.data_properties:
            data_prop_lines.extend(_format_data_property_change(change))
        sections.append("Data Properties:\n" + "\n".join(data_prop_lines))

    if diff.object_properties:
        obj_prop_lines = []
        for change in diff.object_properties:
            obj_prop_lines.extend(_format_object_property_change(change))
        sections.append("Object Properties:\n" + "\n".join(obj_prop_lines))

    return "\n\n".join(sections)
