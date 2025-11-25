from abc import ABC, abstractmethod
from typing import Literal

from ontology_hydra.ontology.state.models import ClassName, Model, OntologyState, PropertyName


class BaseRequirement(Model, ABC):
    @abstractmethod
    def is_satisfied(self, state: OntologyState) -> bool:
        raise NotImplementedError


type ResourceKind = Literal["class", "data_property", "object_property", "any_property"]


class RequiresPresence(BaseRequirement):
    """Requirement that a resource exists or does not exist in the ontology."""

    kind: ResourceKind
    """Kind of the resource (class, data prop, object prop, any prop)"""

    name: ClassName | PropertyName
    """Name of the resource"""

    exists: bool = True
    """Denotes if the resource should exist or not."""

    def is_satisfied(self, state: OntologyState) -> bool:
        exists = (
            (self.kind == "class" and state.get_class(self.name) is not None)
            or (self.kind == "data_property" and state.get_data_property(self.name) is not None)
            or (self.kind == "object_property" and state.get_object_property(self.name) is not None)
            or (self.kind == "any_property" and (state.get_property(self.name) is not None))
        )

        return exists == self.exists
