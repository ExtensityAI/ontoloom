from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.models import ClassName, Description
from ontology_hydra.utils.schema.llm import DataModel


class MergeClassesOperation(DataModel):
    """Merges multiple classes into a single class"""

    op: Literal["merge_classes"] = "merge_classes"

    source_classes: list[ClassName] = Field(
        description="Names of the classes to merge (will be removed)"
    )
    target_name: ClassName = Field(
        description="Name of the merged class (can be new or one of the source classes)"
    )
    description: Description = Field(
        description="Description for the merged class",
    )
