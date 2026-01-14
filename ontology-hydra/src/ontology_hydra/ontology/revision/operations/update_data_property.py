from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.models import (
    ClassExpression,
    DataType,
    Description,
    PropertyName,
    is_none,
)
from ontology_hydra.utils.schema.llm import DataModel


class UpdateDataPropertyOperation(DataModel):
    """Updates an existing data property in the ontology"""

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
        None, description="New literal datatype range. Omit if no change.", exclude_if=is_none
    )
