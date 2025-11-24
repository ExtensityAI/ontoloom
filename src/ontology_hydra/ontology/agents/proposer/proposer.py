from typing import cast

from pydantic import Field
from symai.components import Expression
from symai.strategy import contract

from ontology_hydra.ontology.state.models import Model, OntologyState
from ontology_hydra.ontology.state.ops.types import OperationArgs


class Proposal(Model):
    ops: list[OperationArgs] = Field(
        ..., description="All operations that are required to achieve your proposal"
    )
    summary: str = Field(
        ...,
        description="Summarize your proposal and explain in detail why it is needed.",
    )
    title: str = Field(..., description="Title for your proposal. Make it short and descriptive.")


class ProposerInput(Model):
    intent: str = Field(..., description="User intent")
    state: OntologyState = Field(..., description="Current state of the ontology")
    samples: list[str] = Field(..., description="List of sample texts to analyze")


@contract(post_remedy=True, accumulate_errors=True)
class Proposer(Expression):
    def forward(self, input: ProposerInput) -> Proposal:  # pyright: ignore[reportIncompatibleMethodOverride] # known issue, can ignore
        if self.contract_result is None:
            msg = f"Proposer contract failed! Input was {input}"
            raise ValueError(msg)

        return self.contract_result

    def post(self, _: Proposal):
        return True

    def prompt(self):  # pyright: ignore[reportIncompatibleMethodOverride] # known issue, can ignore
        return "You are an ontology engineer. You are given an ontology state `state`, a list of data samples `samples` and some user intent `intent`. Your task is to propose changes to the current ontology to improve the current ontology with regard to both user intent and data samples."


def propose_changes(state: OntologyState, samples: list[str], intent: str):
    proposer = cast("Proposer", Proposer())

    output: Proposal = proposer(input=ProposerInput(intent=intent, state=state, samples=samples))

    # TODO: validate that operations are valid given the current ontology state
    # TODO: maybe also validate if there are any obvious issues and allow proposer to fix them?

    return output
