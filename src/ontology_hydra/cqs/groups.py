from logging import getLogger
from typing import Literal, cast

from pydantic import Field
from symai import Expression
from symai.components import MetadataTracker
from symai.strategy import LLMDataModel, contract

from ontology_hydra.prompts import prompt_registry
from ontology_hydra.utils.general import begin_tracking

logger = getLogger("ontopipe.cqs")


class Priority(LLMDataModel):
    reason: str = Field(..., description="Why this priority was assigned")
    value: Literal["high", "medium", "low"]


class Group(LLMDataModel):
    name: str
    description: str
    priority: Priority


class Groups(LLMDataModel):
    items: list[Group]


class DomainDefinition(LLMDataModel):
    domain: str = Field(..., description="The domain of the ontology")


@contract(
    pre_remedy=False,
    post_remedy=True,
    accumulate_errors=False,
    verbose=True,
    remedy_retry_params={
        "tries": 25,
        "delay": 0.5,
        "max_delay": 15,
        "jitter": 0.1,
        "backoff": 2,
        "graceful": False,
    },
)
class GroupsGenerator(Expression):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def forward(self, _: DomainDefinition) -> Groups:
        if self.contract_result is None:
            msg = "Contract failed!"
            raise ValueError(msg)

        return self.contract_result

    def post(self, _: Groups) -> bool:
        return True

    @property
    def prompt(self) -> str:
        return prompt_registry.instruction("generate_groups")


def generate_groups_for_domain(domain: str):
    generator = cast("GroupsGenerator", GroupsGenerator())
    with begin_tracking() as tracker:
        x: Groups = generator(input=DomainDefinition(domain=domain))

        generator.contract_perf_stats()
        logger.debug("API Usage: %s", tracker.usage)

    return x.items
