from collections import defaultdict
from collections.abc import Callable
from typing import Literal

from ontology_hydra.ontology.state.models import OntologyState, vartuple
from ontology_hydra.ontology.state.ops.add_class import AddClassOperation, apply_add_class
from ontology_hydra.ontology.state.ops.add_data_property import (
    AddDataPropertyArgs,
    apply_add_data_property,
)
from ontology_hydra.ontology.state.ops.add_object_property import (
    AddObjectPropertyOperation,
    apply_add_object_property,
)
from ontology_hydra.ontology.state.ops.del_class import (
    DeleteClassOperation,
    apply_delete_class,
)
from ontology_hydra.ontology.state.ops.results import OperationResult
from ontology_hydra.ontology.state.ops.types import OperationArgs
from ontology_hydra.ontology.state.ops.update_class import (
    UpdateClassOperation,
    apply_update_class,
)
from ontology_hydra.ontology.state.ops.update_data_property import (
    UpdateDataPropertyOperation,
    apply_update_data_property,
)
from ontology_hydra.ontology.state.ops.update_object_property import (
    UpdateObjectPropertyOperation,
    apply_update_object_property,
)
from ontology_hydra.utils.results import BaseFailure, BaseSuccess, Model


class OperationInapplicableIssue(Model):
    """An operation could not be applied."""

    type: Literal["bad_op"] = "bad_op"
    operation: OperationArgs
    reason: str


Issue = OperationInapplicableIssue


class Failure(BaseFailure):
    issues: list[Issue]


class Success(BaseSuccess):
    state: OntologyState


def _extract_ops_of_type[T: OperationArgs](ops: list[OperationArgs], op_type: type[T]):
    return (
        [op for op in ops if isinstance(op, op_type)],
        [op for op in ops if not isinstance(op, op_type)],
    )


def apply_ops_of_type[T: OperationArgs](
    state: OntologyState,
    ops: list[OperationArgs],
    op_type: type[T],
    apply: Callable[[OntologyState, T], OperationResult],
):
    """Applies all operations of a given type to the ontology state. Returns the new state and the remaining operations."""

    ops_of_type, remaining_ops = _extract_ops_of_type(ops, op_type)

    for op in ops_of_type:
        result = apply(state, op)

        if result.success is True:
            state = result.state

    return state, remaining_ops


def apply(state: OntologyState, ops: list[OperationArgs]):
    # TODO: validate operations list. A specific class/property name can only appear in one of ADD/DELETE/UPDATE ops.
    issues = list[Issue]()

    # first delete properties as nothing depends on them and they might be recreated by the model again
    state, ops = apply_ops_of_type(state, ops, DeleteClassOperation, apply_delete_class)

    # next delete classes as they might be recreated by the model again
    state, ops = apply_ops_of_type(state, ops, DeleteClassOperation, apply_delete_class)

    # finally add classes as other operations might depend on them
    state, ops = apply_ops_of_type(state, ops, AddClassOperation, apply_add_class)

    state, ops = apply_ops_of_type(state, ops, AddDataPropertyArgs, apply_add_data_property)
    state, ops = apply_ops_of_type(
        state, ops, AddObjectPropertyOperation, apply_add_object_property
    )

    state, ops = apply_ops_of_type(state, ops, UpdateClassOperation, apply_update_class)
    state, ops = apply_ops_of_type(
        state, ops, UpdateDataPropertyOperation, apply_update_data_property
    )
    state, ops = apply_ops_of_type(
        state, ops, UpdateObjectPropertyOperation, apply_update_object_property
    )

    assert len(ops) == 0, f"Some operations were not applied: {ops}"  # TODO: make exception

    return Failure(issues=issues) if len(issues) > 0 else Success(state=state)
