from typing import Literal

from ontology_hydra.ontology.agents.updater.tools.tool import BaseToolArgs


class CompleteToolArgs(BaseToolArgs):
    """Indicates that the proposal is complete and no further changes are needed."""

    type: Literal["complete"] = "complete"
