from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.models import (
    ClassExpression,
    Description,
    PropertyName,
    is_none,
)
from ontology_hydra.utils.schema.llm import DataModel


class UpdateObjectPropertyOperation(DataModel):
    """Updates an existing object property in the ontology"""

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
