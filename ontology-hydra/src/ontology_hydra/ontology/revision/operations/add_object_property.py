from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.models import (
    ClassExpression,
    Description,
    PropertyName,
)
from ontology_hydra.utils.schema.llm import DataModel


class AddObjectPropertyOperation(DataModel):
    """Adds a new object property to the ontology"""

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
