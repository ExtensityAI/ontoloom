from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.models import ClassName, Description, is_none
from ontology_hydra.utils.schema.llm import DataModel


class UpdateClassOperation(DataModel):
    """Updates an existing class in the ontology"""

    op: Literal["update_class"] = "update_class"

    name: ClassName = Field(description="Name of the class to update")
    new_name: ClassName | None = Field(
        None,
        description="New name for the class (if renaming). Omit if no change.",
        exclude_if=is_none,
    )
    description: Description | None = Field(
        None, description="New description for the class. Omit if no change.", exclude_if=is_none
    )
    sub_class_of: list[ClassName] | None = Field(
        None,
        description="New superclasses for rdfs:subClassOf (replaces existing). Omit if no change.",
        exclude_if=is_none,
    )
