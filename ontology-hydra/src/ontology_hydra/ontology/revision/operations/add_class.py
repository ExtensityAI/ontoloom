from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.models import ClassName, Description
from ontology_hydra.utils.schema.llm import DataModel


class AddClassOperation(DataModel):
    """Adds a new class to the ontology"""

    op: Literal["add_class"] = "add_class"

    name: ClassName = Field(description="Name of the new class")
    description: Description = Field(description="Description of the new class")
    sub_class_of: list[ClassName] = Field(
        description="Superclasses for rdfs:subClassOf (supports multiple inheritance).",  # TODO: improve description here
    )
