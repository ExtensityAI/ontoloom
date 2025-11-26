from typing import Literal, cast

from pydantic import Field

from ontology_hydra.ontology.state.models import (
    ClassName,
    ObjectProperty,
    OntologyState,
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
    replace_object_property,
    replace_ontology_state,
)


class UpdateObjectPropertyOperationArgs(BaseOperationArgs):
    """Update an existing object property in the ontology."""

    type: Literal["update_obj_prop"] = "update_obj_prop"

    name: PropertyName = Field(..., description="Name of the property to update")

    new_name: PropertyName | None = Field(
        None, description="New name for the property (omit if unchanged)"
    )
    new_domain: vartuple[ClassName] | None = Field(
        None, description="New domain classes for the property (omit if unchanged)"
    )
    new_range: vartuple[ClassName] | None = Field(
        None, description="New range classes for the property (omit if unchanged)"
    )

    new_description: str | None = Field(
        None, description="New description of the property (omit if unchanged)"
    )


def _create_preconditions(args: UpdateObjectPropertyOperationArgs):
    preconds: list[ExistencePrecondition] = [
        ExistencePrecondition(
            resource=ResourceRef(kind="object_property", name=args.name), value="existent"
        )
    ]

    # If renaming, the new name must be free.
    if args.new_name:
        preconds += (
            ExistencePrecondition(
                resource=ResourceRef(kind="object_property", name=args.new_name),
                value="non-existent",
            ),
        )

    # If changing domain/range, ensure referenced classes exist.
    if args.new_domain:
        preconds += (
            ExistencePrecondition(
                resource=ResourceRef(kind="class", name=domain_class), value="existent"
            )
            for domain_class in args.new_domain
        )

    if args.new_range:
        preconds += (
            ExistencePrecondition(
                resource=ResourceRef(kind="class", name=range_class), value="existent"
            )
            for range_class in args.new_range
        )

    return tuple(preconds)


def _create_effects(args: UpdateObjectPropertyOperationArgs):
    if not args.new_name:
        # if we are not renaming, there is no relevant effect
        return ()

    return (
        ExistenceEffect(
            resource=ResourceRef(kind="object_property", name=args.name),
            value="non-existent",
        ),
        ExistenceEffect(
            resource=ResourceRef(kind="object_property", name=args.new_name),
            value="existent",
        ),
    )


class UpdateObjectPropertyOperation(BaseOperation[UpdateObjectPropertyOperationArgs]):
    def __init__(self, args: UpdateObjectPropertyOperationArgs):
        super().__init__(args, _create_preconditions(args), _create_effects(args))

    def _apply(self, state: OntologyState):
        old_prop = cast("ObjectProperty", state.get_property(self.args.name))

        # update the property itself
        updated_prop = replace_object_property(
            old_prop,
            name=self.args.new_name or old_prop.name,
            domain=self.args.new_domain or old_prop.domain,
            range=self.args.new_range or old_prop.range,
            description=self.args.new_description or old_prop.description,
        )

        # update the property in the ontology state
        new_props = tuple(
            prop if prop.name != old_prop.name else updated_prop for prop in state.object_properties
        )

        return replace_ontology_state(state, object_properties=new_props)

    @classmethod
    def from_args(cls, args: UpdateObjectPropertyOperationArgs):
        return cls(args)
