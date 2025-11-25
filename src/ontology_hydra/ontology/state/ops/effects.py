from abc import ABC
from typing import Literal

from ontology_hydra.ontology.state.models import Model
from ontology_hydra.ontology.state.ops.resources import ResourceRef


class Effect(Model, ABC):
    """Describes an effect of an operation on the ontology state."""

    pass


class PresenceEffect(Effect):
    """Indicates that an operation ensures a resource is present or absent in the ontology."""

    resource: ResourceRef
    value: Literal["present", "absent"] = "present"
