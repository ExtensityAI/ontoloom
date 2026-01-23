"""Ontology revision operations - all operation types in a single module."""

from typing import Annotated, Literal

from pydantic import Field

from ontology_hydra.ontology.models import (
    ClassExpression,
    ClassName,
    DataType,
    Description,
    PropertyName,
    is_none,
)
from ontology_hydra.utils.schema.llm import DataModel

# ============================================================
# Class Operations
# ============================================================


class AddClass(DataModel):
    """Adds a new class to the ontology."""

    op: Literal["add_class"] = "add_class"

    name: ClassName = Field(description="Name of the new class")
    description: Description = Field(description="Description of the new class")
    sub_class_of: list[ClassName] = Field(
        description="Superclasses for rdfs:subClassOf (supports multiple inheritance)."
    )


class UpdateClass(DataModel):
    """Updates an existing class in the ontology."""

    op: Literal["update_class"] = "update_class"

    name: ClassName = Field(description="Name of the class to update")
    new_name: ClassName | None = Field(
        None,
        description="New name for the class (if renaming). Omit if no change.",
        exclude_if=is_none,
    )
    description: Description | None = Field(
        None,
        description="New description for the class. Omit if no change.",
        exclude_if=is_none,
    )
    sub_class_of: list[ClassName] | None = Field(
        None,
        description="New superclasses for rdfs:subClassOf (replaces existing). Omit if no change.",
        exclude_if=is_none,
    )


class DeleteClass(DataModel):
    """Deletes a class from the ontology."""

    op: Literal["del_class"] = "del_class"

    name: ClassName = Field(description="Name of the class to delete")


class MergeClasses(DataModel):
    """Merges multiple classes into a single class."""

    op: Literal["merge_classes"] = "merge_classes"

    source_classes: list[ClassName] = Field(
        description="Names of the classes to merge (will be removed)"
    )
    target_name: ClassName = Field(
        description="Name of the merged class (can be new or one of the source classes)"
    )
    description: Description = Field(description="Description for the merged class")


# ============================================================
# Data Property Operations
# ============================================================


class AddDataProperty(DataModel):
    """Adds a new data property to the ontology."""

    op: Literal["add_data_prop"] = "add_data_prop"

    name: PropertyName = Field(description="Name of the new data property (camelCase)")
    description: Description = Field(description="Description of the new data property")
    domain: list[ClassExpression] = Field(
        default_factory=list,
        description="Domain classes or intersections (rdfs:domain).",
    )
    range: DataType = Field(description="Literal datatype range (rdfs:range).")


class UpdateDataProperty(DataModel):
    """Updates an existing data property in the ontology."""

    op: Literal["update_data_prop"] = "update_data_prop"

    name: PropertyName = Field(description="Name of the data property to update")
    new_name: PropertyName | None = Field(
        None,
        description="New name for the data property (if renaming). Omit if no change.",
        exclude_if=is_none,
    )
    description: Description | None = Field(
        None,
        description="New description for the data property. Omit if no change.",
        exclude_if=is_none,
    )
    domain: list[ClassExpression] | None = Field(
        None,
        description="New domain classes or intersections (replaces existing). Omit if no change.",
        exclude_if=is_none,
    )
    range: DataType | None = Field(
        None,
        description="New literal datatype range. Omit if no change.",
        exclude_if=is_none,
    )


class DeleteDataProperty(DataModel):
    """Deletes a data property from the ontology."""

    op: Literal["del_data_prop"] = "del_data_prop"

    name: PropertyName = Field(description="Name of the data property to delete")


# ============================================================
# Object Property Operations
# ============================================================


class AddObjectProperty(DataModel):
    """Adds a new object property to the ontology."""

    op: Literal["add_object_prop"] = "add_object_prop"

    name: PropertyName = Field(description="Name of the new object property (camelCase)")
    description: Description = Field(description="Description of the new object property")
    domain: list[ClassExpression] = Field(
        default_factory=list,
        description="Domain classes or intersections (rdfs:domain).",
    )
    range: list[ClassExpression] = Field(
        default_factory=list,
        description="Range classes or intersections (rdfs:range).",
    )


class UpdateObjectProperty(DataModel):
    """Updates an existing object property in the ontology."""

    op: Literal["update_object_prop"] = "update_object_prop"

    name: PropertyName = Field(description="Name of the object property to update")
    new_name: PropertyName | None = Field(
        None,
        description="New name for the object property (if renaming). Omit if no change.",
        exclude_if=is_none,
    )
    description: Description | None = Field(
        None,
        description="New description for the object property. Omit if no change.",
        exclude_if=is_none,
    )
    domain: list[ClassExpression] | None = Field(
        None,
        description="New domain classes or intersections (replaces existing). Omit if no change.",
        exclude_if=is_none,
    )
    range: list[ClassExpression] | None = Field(
        None,
        description="New range classes or intersections (replaces existing). Omit if no change.",
        exclude_if=is_none,
    )


class DeleteObjectProperty(DataModel):
    """Deletes an object property from the ontology."""

    op: Literal["del_object_prop"] = "del_object_prop"

    name: PropertyName = Field(description="Name of the object property to delete")


Operation = Annotated[
    AddClass
    | UpdateClass
    | DeleteClass
    | MergeClasses
    | AddDataProperty
    | UpdateDataProperty
    | DeleteDataProperty
    | AddObjectProperty
    | UpdateObjectProperty
    | DeleteObjectProperty,
    Field(discriminator="op"),
]
