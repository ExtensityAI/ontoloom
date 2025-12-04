from typing import Literal

from ontology_hydra.ontology.agents.updater.tools.tool import BaseToolArgs
from ontology_hydra.ontology.state.update.ops.types import OperationArgs
from ontology_hydra.types import vartuple


class ApplyOpsToolArgs(BaseToolArgs):
    """Applies a list of operations to the current ontology state."""

    type: Literal["apply_ops"] = "apply_ops"

    ops: vartuple[OperationArgs]
    """A list of operations you want to apply to the current ontology state. The order of operations is expected"""
