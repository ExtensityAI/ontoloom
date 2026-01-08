from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.models import PropertyName
from ontology_hydra.utils.schema.llm import DataModel


class DeleteDataPropertyOperation(DataModel):
    """Deletes a data property from the ontology"""

    op: Literal["del_data_prop"] = "del_data_prop"

    name: PropertyName = Field(description="Name of the data property to delete")
