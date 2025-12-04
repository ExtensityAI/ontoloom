from typing import cast

from pydantic import Field
from symai import Expression
from symai.strategy import contract

from ontology_hydra.ontology.state.models import OntologyState
from ontology_hydra.types import LLMModel


class Proposal(LLMModel):
    context: str = Field(
        ...,
        description="The context and background information considered when formulating the proposal.",
    )
    recommendations: str = Field(
        ...,
        description="A concise list of the main recommendations from the proposal.",
    )
    risks: str = Field(
        "",
        description="A concise list of the main risks and open questions highlighted in the proposal.",
    )
    remarks: str = Field(
        "",
        description="Any additional remarks or considerations about the proposal.",
    )
    title: str = Field(..., description="Title for your proposal. Make it short and descriptive.")


class _Input(LLMModel):
    state: OntologyState = Field(..., description="The current ontology state, including history.")
    intent: str = Field(..., description="The user's high-level goal for the ontology.")
    samples: list[str] = Field(
        ...,
        description="A list of text samples that provide evidence for the intended ontology changes.",
    )


class _Output(LLMModel):
    proposal: Proposal = Field(..., description="The proposed changes to the ontology.")


@contract(post_remedy=True, accumulate_errors=True)
class Proposer(Expression):
    def forward(self, input: _Input) -> _Output:  # pyright: ignore[reportIncompatibleMethodOverride] # known issue, can ignore
        if self.contract_result is None:
            msg = f"Proposer contract failed! Input was {input}"
            raise ValueError(msg)

        return self.contract_result

    def post(self, _: _Output):
        return True

    def prompt(self):  # pyright: ignore[reportIncompatibleMethodOverride] # known issue, can ignore
        return """You are an ontology improvement analyst. Inputs: `state` (current ontology + history), `intent` (user goal), and `samples` (evidence from the domain). Your job is to read all materials, synthesize what the ontology gets wrong or fails to cover, and write a high-level natural-language proposal describing how the ontology should change to better satisfy the intent and fit the data.
    Output expectations:
    - Provide a short descriptive title that captures the single thematic gap you focus on.
    - Populate the `context` section with a narrative overview that summarizes the current ontology limitations and the user intent; reference samples only in aggregate (no quotes or identifiers).
    - Use the `recommendations` section to describe the key thematic improvements needed, staying high-level and narrative rather than enumerating implementation steps.
    - Use the `risks` section to highlight ambiguities, missing evidence, or potential downsides if the recommendation is adopted.
    - Use the `remarks` section for any closing notes, next-questions, or dependencies.
    - Keep recommendations high-level and thematic rather than prescriptive step-by-step edits.
    - Tie each recommendation back to user intent, ontology history, or the generalized evidence from samples so the rationale is clear.
    Restrictions:
    - Pick one coherent thematic area per proposal and explore it in depth instead of covering every possible change.
    - Do NOT leak or quote sample text, email headers, names, or other verbatim content; describe evidence abstractly (e.g., "several messages reference contracting terms").
    - Do NOT enumerate catalogs of specific classes, properties, or IRIs; describe gaps descriptively and focus on why that area matters.
    - Do NOT list explicit ontological entity names, IRIs, or property identifiers—refer to concepts descriptively.
    - Do NOT emit tool calls, JSON, or operation lists; the output is a cohesive narrative proposal meant for humans.
    - Keep the focus on what is missing, what is incorrect, and what should change, not on the mechanics of applying edits."""


def propose_changes(ontology: OntologyState, intent: str, samples: list[str]):
    proposer = cast("Proposer", Proposer())

    output: _Output = proposer(
        _Input(
            state=ontology,
            intent=intent,
            samples=samples,
        )
    )

    return output.proposal
