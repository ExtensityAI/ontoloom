from abc import ABC, abstractmethod
from typing import Literal

from ontology_hydra.ontology.state.models import Model, OntologyState
from ontology_hydra.ontology.state.update.resources import ResourceRef


class Precondition(Model, ABC):
    @abstractmethod
    def is_satisfied_in(self, state: OntologyState) -> bool:
        raise NotImplementedError


class ResourcePrecondition(Precondition):
    """Indicates that an operation places a precondition on a specific resource in the ontology."""

    resource: ResourceRef


class ExistencePrecondition(ResourcePrecondition):
    """Indicates whether a resource must be existent or non-existent in the ontology."""

    value: Literal["existent", "non-existent"] = "existent"
    """Indicates whether the resource must be existent or non-existent."""

    def is_satisfied_in(self, state: OntologyState) -> bool:
        k, n = self.resource.kind, self.resource.name

        exists = (
            (k == "class" and state.get_class(n) is not None)
            or (k == "data_property" and state.get_data_property(n) is not None)
            or (k == "object_property" and state.get_object_property(n) is not None)
            or (k == "any_property" and (state.get_property(n) is not None))
        )

        return exists == (self.value == "existent")
