from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import ClassName, Model


class RemoveClassOperation(Model):
    """Remove an existing class from the ontology."""

    type: Literal["del_class"] = "del_class"

    name: ClassName = Field(..., description="Name of the class to delete")


class RenameClassOperation(Model):
    """Rename an existing class in the ontology."""

    type: Literal["rename_class"] = "rename_class"

    old_name: ClassName = Field(..., description="Current name of the class")
    new_name: ClassName = Field(..., description="New name for the class")

    new_description: str | None = Field(
        None, description="New description of the class (omit if unchanged)"
    )
