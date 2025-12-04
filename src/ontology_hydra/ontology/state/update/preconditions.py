from abc import ABC, abstractmethod
from typing import Literal

from ontology_hydra.ontology.state.models import Model, OntologyState, vartuple
from ontology_hydra.ontology.state.update.resources import ResourceRef


class Precondition(Model, ABC):
    @abstractmethod
    def is_satisfied_in(self, state: OntologyState) -> bool:
        raise NotImplementedError

    def __or__(self, other: "Precondition"):
        return OrPrecondition(subconditions=(self, other))

    def __and__(self, other: "Precondition"):
        return AndPrecondition(subconditions=(self, other))


class ResourcePrecondition(Precondition):
    """Indicates that an operation places a precondition on a specific resource in the ontology."""

    resource: ResourceRef


class OrPrecondition(Precondition):
    """Indicates that at least one of the subconditions must be satisfied"""

    subconditions: vartuple[Precondition]

    def is_satisfied_in(self, state: OntologyState) -> bool:
        return any(option.is_satisfied_in(state) for option in self.subconditions)


class AndPrecondition(Precondition):
    """Indicates that all of the subconditions must be satisfied"""

    subconditions: vartuple[Precondition]

    def is_satisfied_in(self, state: OntologyState) -> bool:
        return all(option.is_satisfied_in(state) for option in self.subconditions)


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
        )

        return exists == (self.value == "existent")

    def __invert__(self):
        """Returns a new ExistencePrecondition with inverted value."""
        inverted_value = "non-existent" if self.value == "existent" else "existent"
        return ExistencePrecondition(resource=self.resource, value=inverted_value)


def and_(*args: Precondition):
    return AndPrecondition(subconditions=args)


def or_(*args: Precondition):
    return OrPrecondition(subconditions=args)


def exists(resource: ResourceRef):
    return ExistencePrecondition(resource=resource, value="existent")
