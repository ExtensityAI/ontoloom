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
from ontology_hydra.ontology.state.ops.base import (
    Success,
)
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


def _as_operation(args: OperationArgs):
    match args:
        case AddClassOperationArgs():
            return AddClassOperation.from_args(args)

        case UpdateClassOperationArgs():
            return UpdateClassOperation.from_args(args)

        case DeleteClassOperationArgs():
            return DeleteClassOperation.from_args(args)

        case AddDataPropertyOperationArgs():
            return AddDataPropertyOperation.from_args(args)

        case UpdateDataPropertyOperationArgs():
            return UpdateDataPropertyOperation.from_args(args)

        case AddObjectPropertyOperationArgs():
            return AddObjectPropertyOperation.from_args(args)

        case UpdateObjectPropertyOperationArgs():
            return UpdateObjectPropertyOperation.from_args(args)

        case DeletePropertyOperationArgs():
            return DeletePropertyOperation.from_args(args)


def apply(state: OntologyState, args: list[OperationArgs]):
    remaining_ops = [_as_operation(arg) for arg in args]

    progress = True

    # try to apply operations until no further progress can be made. Progress is defined as one operation being applied.
    while remaining_ops and progress:
        progress = False

        # try to apply remaining operations
        for op in list(remaining_ops):
            missing_requirements = op.test_for_unsatisfied_requirements(state)

            if len(missing_requirements) > 0:
                # operation not (yet) applicable
                continue

            result = op.try_apply(state)

            if result.success is True:
                # operation applied successfully
                state = result.state
                remaining_ops.remove(op)
                progress = True

            if result.type == "exception":
                # TODO some exception occured, not sure yet how to handle this
                pass
            elif result.type == "unsatisfied_requirements":
                # should not happen, as we already checked for missing requirements
                # TODO maybe raise exception or a warning or sth?
                pass

    return Failure(issues=issues) if len(issues) > 0 else Success(state=state)
