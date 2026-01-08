from symai import Expression

from ontology_hydra.ontology.components.implementation.draft_ops import OperationSequence
from ontology_hydra.ontology.models import Ontology
from ontology_hydra.utils.schema.llm import DataModel

# TODO: if this is not flexible enough, add some sort of state-machine where information can pass between drafter and reviewer and all that, but for now keep it simple?

_ACCEPTED = "ACCEPTED"
_REJECTED = "REJECTED"

_prompt = f"""You are an ontology engineer reviewing whether a proposed sequence of operations correctly implements a plan.

<plan>{{plan}}</plan>
<ops>{{ops}}</ops>
<ontology>{{ontology}}</ontology>

Analyze whether the operations faithfully implement the plan when applied to the current ontology. For each aspect of the plan, verify:
- Coverage: Does the operation sequence address all changes described in the plan?
- Correctness: Are class names, property names, domains, ranges, and hierarchies accurate?
- Consistency: Do the operations maintain ontology coherence (no dangling references, valid inheritance)?
- Completeness: Are there missing operations the plan implies but aren't present?

Describe any discrepancies you find in a short paragraph for each issue:
- State what the plan specifies vs. what the operations do
- Explain the impact on the ontology if applied as-is
- Suggest what correction is needed

Write prose, not tables or bullet lists. Be specific and reference the plan and operations directly.

End your review with exactly '{_ACCEPTED}' or '{_REJECTED}' (plain text, no formatting or punctuation after)."""


class Review(DataModel):
    accepted: bool
    text: str


# TODO: provide the reviewer with the NEW ontology AFTER execution of ops


def review_ops(plan: str, ops: OperationSequence, ontology: Ontology):
    """Reviews whether a sequence of operations implements the given plan when applied to the ontology."""

    # use raw prompting to get a raw review and nothing else.
    # TODO: consider contract - why not?
    review: str = Expression.prompt(
        _prompt.format(plan=plan, ops=ops.model_dump_json(), ontology=ontology.model_dump_json())
    ).value.strip()

    # as a safety net, we also accept bold formatted verdicts
    if review.endswith(_ACCEPTED) or review.endswith(f"**{_ACCEPTED}**"):
        accepted = True
    elif review.endswith(_REJECTED) or review.endswith(f"**{_REJECTED}**"):
        accepted = False
    else:
        msg = "Review did not end with ACCEPTED or REJECTED"
        raise ValueError(msg)

    return Review(accepted=accepted, text=review)
