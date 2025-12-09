from typing import Literal

from pydantic import Field

from ontology_hydra.ontology.state.models import Class, ClassName, OntologyState
from ontology_hydra.ontology.state.update.ops.base import BaseOperation
from ontology_hydra.ontology.state.utils import replace_class, replace_ontology_state


def _replace_parent_name_if_required(cls: Class, old_name: ClassName, new_name: ClassName):
    if cls.parent == old_name:
        return Class(
            name=cls.name,
            parent=new_name,
            description=cls.description,
        )

    return cls


class UpdateClassOperation(BaseOperation):
    """Updates an existing class in the ontology."""

    type: Literal["update_class"] = "update_class"

    name: ClassName = Field(..., description="Name of the class to update")
    new_name: ClassName | None = Field(
        None, description="New name for the class (omit if unchanged)"
    )
    new_description: str | None = Field(
        None, description="New description of the class (omit if unchanged)"
    )

    def describe(self):
        changes = list[str]()
        if self.new_name and self.new_name != self.name:
            changes.append(f"name to '{self.new_name}'")
        if self.new_description and self.new_description != "":
            changes.append(f"description to '{self.new_description}'")
        changes_str = " and ".join(changes)
        return f"Update class '{self.name}': set {changes_str}"

    def _apply(self, state: OntologyState):
        old_class = state.get_class(self.name)
        if not old_class:
            msg = f"Class '{self.name}' does not exist"
            raise ValueError(msg)

        if self.new_name and self.new_name != self.name and state.get_class(self.new_name):
            msg = f"Class '{self.new_name}' already exists"
            raise ValueError(msg)

        # update the class itself
        updated_class = replace_class(
            old_class,
            name=self.new_name or old_class.name,
            description=self.new_description or old_class.description,
            parent=old_class.parent,
        )

        # update references to this class in other classes' parent fields
        new_classes = tuple(
            _replace_parent_name_if_required(cls, old_class.name, updated_class.name)
            if cls.name != old_class.name
            else updated_class
            for cls in state.classes
        )

        return replace_ontology_state(state, classes=new_classes)
