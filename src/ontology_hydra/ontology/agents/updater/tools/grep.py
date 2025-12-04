from typing import Literal

from ontology_hydra.ontology.agents.updater.tools.tool import BaseToolArgs


class GrepToolArgs(BaseToolArgs):
    type: Literal["grep"] = "grep"

    search: str
    """The name/... you want to search the ontology for"""
