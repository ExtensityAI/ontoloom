from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.models import (
    ClassExpression,
    DataType,
    Description,
    PropertyName,
)
from ontology_hydra.utils.schema.llm import DataModel


class AddDataPropertyOperation(DataModel):
    """Adds a new data property to the ontology"""

    op: Literal["add_data_prop"] = "add_data_prop"

    name: PropertyName = Field(description="Name of the new data property (camelCase)")
    description: Description = Field(description="Description of the new data property")
    domain: list[ClassExpression] = Field(
        default_factory=list,
        description="Domain classes or intersections (rdfs:domain).",
    )
    range: DataType = Field(description="Literal datatype range (rdfs:range).")
