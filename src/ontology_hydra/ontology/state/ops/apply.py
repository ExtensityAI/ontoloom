from typing import Literal

from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.ontology.state.ops.add_class import (
    AddClassOperation,
    AddClassOperationArgs,
)
from ontology_hydra.ontology.state.ops.add_data_property import (
    AddDataPropertyOperation,
    AddDataPropertyOperationArgs,
)
from ontology_hydra.ontology.state.ops.add_object_property import (
    AddObjectPropertyOperation,
    AddObjectPropertyOperationArgs,
)
from ontology_hydra.ontology.state.ops.base import BaseOperation, OperationResult
from ontology_hydra.ontology.state.ops.del_class import (
    DeleteClassOperation,
    DeleteClassOperationArgs,
)
from ontology_hydra.ontology.state.ops.del_property import (
    DeletePropertyOperation,
    DeletePropertyOperationArgs,
)
from ontology_hydra.ontology.state.ops.types import OperationArgs
from ontology_hydra.ontology.state.ops.update_class import (
    UpdateClassOperation,
    UpdateClassOperationArgs,
)
from ontology_hydra.ontology.state.ops.update_data_property import (
    UpdateDataPropertyOperation,
    UpdateDataPropertyOperationArgs,
)
from ontology_hydra.ontology.state.ops.update_object_property import (
    UpdateObjectPropertyOperation,
    UpdateObjectPropertyOperationArgs,
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


def _as_operation(arg: OperationArgs) -> BaseOperation:
    if isinstance(arg, AddClassOperationArgs):
        return AddClassOperation(arg)
    if isinstance(arg, UpdateClassOperationArgs):
        return UpdateClassOperation(arg)
    if isinstance(arg, DeleteClassOperationArgs):
        return DeleteClassOperation(arg)
    if isinstance(arg, AddObjectPropertyOperationArgs):
        return AddObjectPropertyOperation(arg)
    if isinstance(arg, UpdateObjectPropertyOperationArgs):
        return UpdateObjectPropertyOperation(arg)
    if isinstance(arg, AddDataPropertyOperationArgs):
        return AddDataPropertyOperation(arg)
    if isinstance(arg, UpdateDataPropertyOperationArgs):
        return UpdateDataPropertyOperation(arg)
    if isinstance(arg, DeletePropertyOperationArgs):
        return DeletePropertyOperation(arg)

    msg = f"Unsupported operation args: {type(arg)}"
    raise TypeError(msg)


def _unsatisfied_requirements(op: BaseOperation, state: OntologyState):
    return tuple(req for req in op.requires() if not req.is_satisfied(state))


def apply(state: OntologyState, ops: list[OperationArgs]):
    issues = list[Issue]()
    operations = [_as_operation(op) for op in ops]

    remaining_ops = operations.copy()
    progress = True

    while remaining_ops and progress:
        progress = False

        for op in list(remaining_ops):
            missing_requirements = _unsatisfied_requirements(op, state)
            if len(missing_requirements) > 0:
                continue

            result: OperationResult = op.apply(state)
            remaining_ops.remove(op)

            if result.success is True:
                state = result.state
            else:
                issues.append(OperationInapplicableIssue(operation=op.args, reason=result.reason))

            progress = True

        if not progress and remaining_ops:
            for op in remaining_ops:
                missing = _unsatisfied_requirements(op, state)
                missing_reasons = "; ".join(req.describe(state) for req in missing)
                issues.append(
                    OperationInapplicableIssue(
                        operation=op.args,
                        reason=f"Requirements not satisfied: {missing_reasons}",
                    )
                )

    return Failure(issues=issues) if len(issues) > 0 else Success(state=state)
