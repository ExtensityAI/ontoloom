from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.models import PropertyName
from ontology_hydra.utils.schema.llm import DataModel


class DeleteObjectPropertyOperation(DataModel):
    """Deletes an object property from the ontology"""

    op: Literal["del_object_prop"] = "del_object_prop"

    name: PropertyName = Field(description="Name of the object property to delete")
