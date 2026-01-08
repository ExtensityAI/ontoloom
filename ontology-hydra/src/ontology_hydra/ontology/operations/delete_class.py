from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.models import ClassName
from ontology_hydra.utils.schema.llm import DataModel


class DeleteClassOperation(DataModel):
    """Deletes a class from the ontology"""

    op: Literal["del_class"] = "del_class"

    name: ClassName = Field(description="Name of the class to delete")
