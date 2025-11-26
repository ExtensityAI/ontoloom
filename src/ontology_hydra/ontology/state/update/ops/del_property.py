from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import OntologyState, PropertyName
from ontology_hydra.ontology.state.update.effects import ExistenceEffect
from ontology_hydra.ontology.state.update.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.update.preconditions import ExistencePrecondition
from ontology_hydra.ontology.state.update.resources import ResourceRef
from ontology_hydra.ontology.state.utils import replace_ontology_state


class DeletePropertyOperationArgs(BaseOperationArgs):
    """Remove an existing object/data property from the ontology."""

    type: Literal["del_prop"] = "del_prop"

    name: PropertyName = Field(..., description="Name of the object/data property to delete")


def _create_preconditions(args: DeletePropertyOperationArgs):
    # Property must exist (data or object).
    return (
        ExistencePrecondition(
            resource=ResourceRef(kind="any_property", name=args.name), value="existent"
        ),
    )


def _create_effects(args: DeletePropertyOperationArgs):
    return (
        ExistenceEffect(
            resource=ResourceRef(kind="any_property", name=args.name), value="non-existent"
        ),
    )


class DeletePropertyOperation(BaseOperation[DeletePropertyOperationArgs]):
    def __init__(self, args: DeletePropertyOperationArgs):
        super().__init__(args, _create_preconditions(args), _create_effects(args))

    def _apply(self, state: OntologyState):
        # Remove the property from both lists; only one will actually match.
        data_props = tuple(prop for prop in state.data_properties if prop.name != self.args.name)
        object_props = tuple(
            prop for prop in state.object_properties if prop.name != self.args.name
        )

        return replace_ontology_state(
            state, data_properties=data_props, object_properties=object_props
        )

    @classmethod
    def from_args(cls, args: DeletePropertyOperationArgs):
        return cls(args)
