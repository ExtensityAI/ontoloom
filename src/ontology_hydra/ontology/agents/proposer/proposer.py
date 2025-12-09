from typing import Literal, cast

from pydantic import Field
from symai import Expression
from symai.strategy import contract

from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.ontology.state.update.ops.types import Operation
from ontology_hydra.types import LLMModel, vartuple


class Thought(LLMModel):
    type: Literal["thought"] = "thought"
    content: str = Field(
        ...,
        description="A short bullet point thought explaining the reasoning behind the following operation(s). Use this to explain how you evaluated the intent, state, and samples, and how your operation(s) fit the remaining budget.",
    )


class WorkingDraft(LLMModel):
    description: str = Field(
        ...,
        description="Describes what this proposal is about.",
    )

    content: vartuple[Operation | Thought] = Field(
        ...,
        description="A list of operations that, when applied to the ontology, will implement this proposal.",
    )


class ProposalUpdate(LLMModel):
    description: str | None = Field(
        None,
        description="Describes what this proposal update is about. Omit if you are not changing the description.",
    )

    content: vartuple[Operation | Thought] | None = Field(
        None,
        description="A list of operations that, when applied to the ontology, will implement this proposal update. Omit if you are not changing the operations.",
    )


class _Input(LLMModel):
    state: OntologyState = Field(..., description="The current ontology state.")
    intent: str = Field(..., description="The user's high-level goal for the ontology.")

    draft: WorkingDraft = Field(
        ...,
        description="Your working draft of the proposal. Your task is to refine and finalize it based on the input state, intent, and samples.",
    )


class _Output(LLMModel):
    update: ProposalUpdate = Field(..., description="An update to your proposal.")
    completed: bool = Field(
        ...,
        description=(
            "Whether the proposal is now complete and ready to be submitted. "
            "Only set to true if you believe the proposal is fully formed and actionable. "
            "Try to be close to the given budget when marking as complete."
        ),
    )


@contract(post_remedy=True, accumulate_errors=True)  # pyright: ignore[reportUntypedClassDecorator]
class Proposer(Expression):
    def forward(self, input: _Input) -> _Output:  # pyright: ignore[reportIncompatibleMethodOverride] # known issue, can ignore
        if self.contract_result is None:
            msg = f"Proposer contract failed! Input was {input}"
            raise ValueError(msg)

        return self.contract_result

    def post(self, _: _Output):
        return True

    def prompt(self):  # pyright: ignore[reportIncompatibleMethodOverride] # known issue, can ignore
        return (
            "You are an ontology improvement analyst operating under a strict budget. "
            "Inputs: `state` (current ontology + history), `intent` (user goal), optional `samples` "
            "(evidence from the domain; may be summarized as 'no samples provided'), `proposal` (your current draft), and `budget` "
            "(remaining credits for refinement). Your job is to read all materials, reason "
            "stepwise about the highest-value improvements, and emit an incremental update "
            "to the proposal that fits within the available budget.\n"
            "Output expectations:\n"
            "- Populate `reasoning` with short bullet thoughts that explain how you evaluated the intent, state, and samples, and how your update fits the remaining budget.\n"
            "- Provide a concise `update` that improves the proposal: adjust the description and/or modify the operations list to close gaps.\n"
            "- Set `completed` to true only when the proposal is fully actionable or the remaining budget would be better saved than spent on further iteration.\n"
            "Restrictions:\n"
            "- Avoid unnecessary churn; prefer incremental improvements over rewrites when budget is low.\n"
            "- Do NOT quote samples verbatim; describe evidence abstractly.\n"
            "- Keep reasoning focused on coverage gaps, alignment with intent, and why the proposed operations are the best use of the remaining budget."
        )


def propose_changes(
    ontology: OntologyState,
    intent: str,
) -> WorkingDraft:
    proposer = cast("Proposer", Proposer())

    draft = WorkingDraft(
        description="change me",
        content=(),
    )

    current_draft = draft

    while True:
        input_data = _Input(
            state=ontology,
            intent=intent,
            draft=current_draft,
        )

        output = proposer(input_data)

        update = output.update

        current_draft = WorkingDraft(
            description=update.description or current_draft.description,
            content=update.content or current_draft.content,
        )

        if output.completed:
            break

    return current_draft
