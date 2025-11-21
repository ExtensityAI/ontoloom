from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.growth.models import (
    ClassName,
    Model,
    PrimitiveDataType,
    PropertyName,
    vartuple,
)


class AddObjectPropertyOperation(Model):
    """Add a new object property to the ontology."""

    type: Literal["add_obj_prop"] = "add_obj_prop"

    name: PropertyName = Field(..., description="Name of the property to add")
    domain: vartuple[ClassName] = Field(
        ..., description="Domain classes for the property"
    )  # TODO: what if domain is both applied to class and it's subclass? is that allowed?
    range: vartuple[ClassName] = Field(..., description="Range classes for the property")

    description: str | None = Field(None, description="Description of the property to add")


class UpdateObjectPropertyOperation(Model):
    """Update an existing object property in the ontology."""

    type: Literal["update_obj_prop"] = "update_obj_prop"

    name: PropertyName = Field(..., description="Name of the property to update")

    new_domain: vartuple[ClassName] = Field(..., description="New domain classes for the property")
    new_range: vartuple[ClassName] = Field(..., description="New range classes for the property")

    new_description: str | None = Field(
        None, description="New description of the property (omit if unchanged)"
    )


class AddDataPropertyOperation(Model):
    """Add a new data property to the ontology."""

    type: Literal["add_data_prop"] = "add_data_prop"

    name: PropertyName = Field(..., description="Name of the property to add")
    domain: vartuple[ClassName] = Field(..., description="Domain classes for the property")
    range: PrimitiveDataType = Field(..., description="Range data types for the property")

    description: str | None = Field(None, description="Description of the property to add")


class UpdateDataPropertyOperation(Model):
    """Update an existing data property in the ontology."""

    type: Literal["update_data_prop"] = "update_data_prop"

    name: PropertyName = Field(..., description="Name of the property to update")

    new_domain: vartuple[ClassName] = Field(..., description="New domain classes for the property")
    new_range: PrimitiveDataType = Field(..., description="New range data types for the property")

    new_description: str | None = Field(
        None, description="New description of the property (omit if unchanged)"
    )


class RenamePropertyOperation(Model):
    """Rename an existing property in the ontology."""

    type: Literal["rename_prop"] = "rename_prop"

    old_name: PropertyName = Field(..., description="Current name of the property")
    new_name: PropertyName = Field(..., description="New name for the property")

    new_description: str | None = Field(
        None, description="New description of the property (omit if unchanged)"
    )


class RemovePropertyOperation(Model):
    """Remove an existing property from the ontology."""

    type: Literal["del_prop"] = "del_prop"

    name: PropertyName = Field(..., description="Name of the property to delete")
