from abc import ABC
from typing import Literal

from ontology_hydra.ontology.state.models import Model
from ontology_hydra.ontology.state.update.resources import ResourceRef


class Effect(Model, ABC):
    """Describes an effect of an operation on the ontology state."""

    pass


class ExistenceEffect(Effect):
    """Indicates that an operation ensures a resource is existent or non-existent in the ontology."""

    resource: ResourceRef
    value: Literal["existent", "non-existent"] = "existent"
