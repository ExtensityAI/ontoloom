from typing import Annotated

from pydantic import Field

from ontology_hydra.ontology.growth.agents.proposer.ops.classes import (
    AddClassOperation,
    RemoveClassOperation,
    RenameClassOperation,
)
from ontology_hydra.ontology.growth.agents.proposer.ops.props import (
    AddDataPropertyOperation,
    AddObjectPropertyOperation,
    RemovePropertyOperation,
    RenamePropertyOperation,
    UpdateDataPropertyOperation,
    UpdateObjectPropertyOperation,
)

Operation = Annotated[
    # classes
    AddClassOperation
    | RenameClassOperation
    | RemoveClassOperation
    # properties
    | AddObjectPropertyOperation
    | AddDataPropertyOperation
    | UpdateObjectPropertyOperation
    | UpdateDataPropertyOperation
    | RenamePropertyOperation
    | RemovePropertyOperation,
    Field(discriminator="type"),
]


__all__ = ["Operation"]
