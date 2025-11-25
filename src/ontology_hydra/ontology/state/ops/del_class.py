from typing import Literal

from pydantic import Field

from dataclasses import dataclass

from ontology_hydra.ontology.state.models import (
    ClassName,
    DataProperty,
    Model,
    ObjectProperty,
    OntologyState,
)
from ontology_hydra.ontology.state.ops.base import (
    BaseOperation,
    OperationFailure,
    OperationResult,
    OperationSuccess,
    Provision,
    Requirement,
)
from ontology_hydra.ontology.state.ops.utils import (
    replace_data_property,
    replace_object_property,
    replace_ontology_state,
)


class DeleteClassOperationArgs(Model):
    """Remove an existing class from the ontology."""

    type: Literal["del_class"] = "del_class"

    name: ClassName = Field(..., description="Name of the class to delete")


def _remove_class_from_data_property(class_name: ClassName, prop: DataProperty):
    new_domain = tuple(dom for dom in prop.domain if dom != class_name)

    return replace_data_property(prop, domain=new_domain)


def _remove_class_from_object_property(
    class_name: ClassName, prop: ObjectProperty
) -> ObjectProperty:
    new_domain = tuple(dom for dom in prop.domain if dom != class_name)
    new_range = tuple(rng for rng in prop.range if rng != class_name)

    return replace_object_property(prop, domain=new_domain, range=new_range)


def apply_delete_class(state: OntologyState, op: DeleteClassOperationArgs) -> OperationResult:
    if (target := state.get_class(op.name)) is None:
        return OperationFailure(reason=f"Class '{op.name}' does not exist in the ontology.")

    # we also need to remove all subclasses recursively
    subclasses = state.get_subclasses(target.name)

    for subclass in subclasses:
        # implicitly create a remove op for the subclass and recursively remove it
        result = apply_delete_class(
            state,
            DeleteClassOperationArgs(name=subclass.name),
        )

        if result.success is False:
            # TODO: improve error here, though this should never happen. we want to provide better context on which operation originated this error
            return OperationFailure(reason=result.reason)

        # update state, the subclass has been deleted
        state = result.state

        # TODO: also consider that at some point, some properties might have NO DOMAIN/RANGE left, we definitely want to penalize this in the judge

    # remove from classes
    new_classes = tuple(c for c in state.classes if c != target)

    # remove from domain and range in obj props
    new_object_properties = tuple(
        _remove_class_from_object_property(target.name, prop) for prop in state.object_properties
    )

    # remove from domain in data props
    new_data_properties = tuple(
        _remove_class_from_data_property(target.name, prop) for prop in state.data_properties
    )

    return OperationSuccess(
        state=replace_ontology_state(
            state,
            classes=new_classes,
            object_properties=new_object_properties,
            data_properties=new_data_properties,
        )
    )


@dataclass(frozen=True, slots=True)
class DeleteClassOperation(BaseOperation[DeleteClassOperationArgs]):
    def requires(self) -> tuple[Requirement, ...]:
        return (Requirement(kind="class", name=self.args.name, exists=True),)

    def provides(self) -> tuple[Provision, ...]:
        return (Provision(kind="class", name=self.args.name, exists=False),)

    def apply(self, state: OntologyState) -> OperationResult:
        return apply_delete_class(state, self.args)
