from typing import Literal, cast

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    DataProperty,
    OntologyState,
    PrimitiveDataType,
    PropertyName,
    vartuple,
)
from ontology_hydra.ontology.state.update.effects import ExistenceEffect
from ontology_hydra.ontology.state.update.ops.base import (
    BaseOperation,
    BaseOperationArgs,
)
from ontology_hydra.ontology.state.update.preconditions import ExistencePrecondition
from ontology_hydra.ontology.state.update.resources import ResourceRef
from ontology_hydra.ontology.state.utils import (
    replace_data_property,
    replace_ontology_state,
)


class UpdateDataPropertyOperationArgs(BaseOperationArgs):
    """Update an existing data property in the ontology."""

    type: Literal["update_data_prop"] = "update_data_prop"

    name: PropertyName = Field(..., description="Name of the property to update")

    new_name: PropertyName | None = Field(
        None, description="New name for the property (omit if unchanged)"
    )

    new_domain: vartuple[ClassName] | None = Field(
        None, description="New domain classes for the property (omit if unchanged)"
    )
    new_range: PrimitiveDataType | None = Field(
        None, description="New range data type for the property (omit if unchanged)"
    )

    new_description: str | None = Field(
        None, description="New description of the property (omit if unchanged)"
    )


def _create_preconditions(args: UpdateDataPropertyOperationArgs):
    preconds: list[ExistencePrecondition] = [
        ExistencePrecondition(
            resource=ResourceRef(kind="data_property", name=args.name), value="existent"
        )
    ]

    # If renaming, the new name must be free.
    if args.new_name:
        preconds.append(
            ExistencePrecondition(
                resource=ResourceRef(kind="data_property", name=args.new_name),
                value="non-existent",
            )
        )

    # If changing domain, ensure every referenced class exists.
    if args.new_domain:
        preconds.extend(
            ExistencePrecondition(
                resource=ResourceRef(kind="class", name=domain_class), value="existent"
            )
            for domain_class in args.new_domain
        )

    return tuple(preconds)


def _create_effects(args: UpdateDataPropertyOperationArgs):
    if not args.new_name:
        # if we are not renaming, there is no relevant effect
        return ()

    return (
        ExistenceEffect(
            resource=ResourceRef(kind="data_property", name=args.name),
            value="non-existent",
        ),
        ExistenceEffect(
            resource=ResourceRef(kind="data_property", name=args.new_name),
            value="existent",
        ),
    )


class UpdateDataPropertyOperation(BaseOperation[UpdateDataPropertyOperationArgs]):
    def __init__(self, args: UpdateDataPropertyOperationArgs):
        super().__init__(args, _create_preconditions(args), _create_effects(args))

    def _apply(self, state: OntologyState):
        old_prop = cast("DataProperty", state.get_property(self.args.name))

        # update the property itself
        updated_prop = replace_data_property(
            old_prop,
            name=self.args.new_name or old_prop.name,
            domain=self.args.new_domain or old_prop.domain,
            range=self.args.new_range or old_prop.range,
            description=self.args.new_description or old_prop.description,
        )

        # update the property in the ontology state
        new_props = tuple(
            prop if prop.name != old_prop.name else updated_prop for prop in state.data_properties
        )

        return replace_ontology_state(state, data_properties=new_props)

    @classmethod
    def from_args(cls, args: UpdateDataPropertyOperationArgs):
        return cls(args)
