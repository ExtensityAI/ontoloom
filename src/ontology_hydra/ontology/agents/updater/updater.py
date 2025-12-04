from typing import cast

from pydantic import Field
from symai.components import Expression
from symai.strategy import contract

from ontology_hydra.ontology.agents.proposer.proposer import Proposal
from ontology_hydra.ontology.agents.updater.tools.types import ToolArgs
from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.types import LLMModel, vartuple


class _Output(LLMModel):
    thought: list[str | ToolArgs] = Field(
        ..., description="Thoughts and tools you want to use. Feel free to mix them."
    )


class ToolCall(LLMModel):
    args: ToolArgs
    """The tool that was called."""

    response: object


HistoryItem = ToolCall


class Input(LLMModel):
    ontology: OntologyState = Field(..., description="Current state of the ontology")
    history: vartuple[HistoryItem] = Field(..., description="Your work history so far")
    proposal: Proposal = Field(..., description="The proposal you are trying to implement")


@contract(post_remedy=True, accumulate_errors=True)
class Updater(Expression):
    def forward(self, input: Input) -> _Output:  # pyright: ignore[reportIncompatibleMethodOverride] # known issue, can ignore
        if self.contract_result is None:
            msg = f"Updater contract failed! Input was {input}"
            raise ValueError(msg)

        return self.contract_result

    def post(self, _: _Output):
        return True

    def prompt(self):  # pyright: ignore[reportIncompatibleMethodOverride] # known issue, can ignore
        return (
            "You are an ontology engineer with tools. Inputs: `state` (ontology + history), "
            "`intent` (user goal), `samples` (evidence). Think stepwise and emit a `thought` list "
            "containing short reasoning strings and tool calls. Available tools:\n"
            "- `grep`: search for classes/properties by name; use to inspect existing concepts before changing them.\n"
            "- `apply_ops`: propose an ordered list of operations to transform the ontology.\n"
            "- `complete`: signal the proposal is final.\n"
            "Guidelines for ops:\n"
            "- Your task is to create the next most important update to the ontology.\n"
            "- Focus on one specific improvement or addition that brings the ontology closer to the intent.\n"
            "- Do not try to do everything at once. Be precise and focused.\n"
            "- Reuse/extend existing classes/properties when possible; avoid redundant add+delete cycles.\n"
            "- Respect obvious preconditions: parents/domains/ranges must exist; new names must be free; "
            "deletions must not leave orphan references; do not delete a class with subclasses.\n"
            "- Prefer updates/renames over delete+add when modifying a resource.\n"
            "- Keep the op list minimal and aligned with the intent and patterns seen in the samples.\n"
            "Protocol:\n"
            "1) Read `history` first. If you need context, use `grep`.\n"
            "2) When ready, call `apply_ops` with the ordered operations.\n"
            "3) Finish with `complete` and include a brief reasoning string just before it summarizing why "
            "the ops satisfy the intent.\n"
            "Return only the `thought` list (no extra text outside the list)."
        )


def apply_proposal(ontology: OntologyState, proposal: Proposal):
    updater = cast("Updater", Updater())

    output: _Output = updater(input=Input(ontology=ontology, history=(), proposal=proposal))

    print(output.model_dump_json(indent=2))

    # TODO: validate that operations are valid given the current ontology state
    # TODO: maybe also validate if there are any obvious issues and allow proposer to fix them?

    return output
