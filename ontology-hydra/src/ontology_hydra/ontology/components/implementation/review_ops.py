from symai import Expression

from ontology_hydra.config import ComponentName
from ontology_hydra.llm.engine import create_component_engine
from ontology_hydra.ontology.revision.diff import diff_ontology, format_diff
from ontology_hydra.ontology.revision.executor import execute_ops
from ontology_hydra.utils.schema.models import DataModel

_ACCEPTED = "ACCEPTED"
_REJECTED = "REJECTED"

_prompt = f"""You are an ontology engineer reviewing whether a proposed sequence of operations correctly implements a plan.

<intent>{{intent}}</intent>
<current_ontology>{{ontology}}</current_ontology>
<plan>{{plan}}</plan>
<ops>{{ops}}</ops>
<diff>{{diff}}</diff>

The current_ontology shows the existing state before the operations are applied. Note that properties with domain on a parent class (e.g. Thing) are inherited by all subclasses.

The diff shows the actual changes that would be applied to the ontology:
  + means added
  - means removed
  ~ means modified

Analyze whether the operations faithfully implement the plan. For each aspect of the plan, verify:
- Coverage: Does the operation sequence address all changes described in the plan?
- Correctness: Are class names, property names, domains, ranges, and hierarchies accurate?
- Consistency: Do the operations maintain ontology coherence (no dangling references, valid inheritance)?
- Completeness: Are there missing operations the plan implies but aren't present?
- Redundancy: Do any new properties duplicate functionality already available via inheritance?
- Side effects: Does the diff show any unintended changes not specified in the plan?

## Quality Checks

In addition to plan faithfulness, reject the operations if any of the following quality issues are present:

**Instance-as-class errors** — Any new subclass that has no distinct properties from its siblings is likely an instance or enum value, not a real class. If the diff adds subclasses that are structurally identical to their siblings (same properties, no new constraints), reject.

**Property duplication** — Any new property whose meaning semantically overlaps with an existing property on the same or a parent class. Check whether a property with similar name or description already exists. If so, reject unless the plan explicitly justifies why both are needed.

**Budget violations** — The operations must not add more than 3 new classes or 5 new properties (data + object combined) in a single iteration. Count the additions in the diff. If exceeded, reject.

**Domain creep** — Any new class that models operational/transactional concerns (e.g., payment processing, order management, customer accounts, UI state) that fall outside the declared intent. If the intent is about a domain topic, reject classes that drift into business operations.

Describe any discrepancies you find in a short paragraph for each issue:
- State what the plan specifies vs. what the operations do
- Explain the impact on the ontology if applied as-is
- Suggest what correction is needed

Write prose, not tables or bullet lists. Be specific and reference the plan and operations directly.

End your review with exactly '{_ACCEPTED}' or '{_REJECTED}' (plain text, no formatting or punctuation after)."""


class Review(DataModel):
    accepted: bool
    text: str


def review_ops(
    config: HydraConfig,
    plan: str,
    ops: OperationSequence,
    ontology: Ontology,
    *,
    intent: str = "",
):
    """Reviews whether a sequence of operations implements the given plan when applied to the ontology."""
    # execute operations to get the resulting ontology
    new_ontology = execute_ops(ontology, ops.ops)
    diff = diff_ontology(ontology, new_ontology)
    diff_text = format_diff(diff)

    with create_component_engine(config, ComponentName.review_ops):
        review: str = Expression.prompt(
            _prompt.format(
                ontology=ontology.model_dump_json(),
                plan=plan,
                ops=ops.model_dump_json(),
                diff=diff_text,
                intent=intent,
            ),
        ).value.strip()

    # as a safety net, we also accept bold formatted verdicts
    if review.endswith((_ACCEPTED, f"**{_ACCEPTED}**")):
        accepted = True
    elif review.endswith((_REJECTED, f"**{_REJECTED}**")):
        accepted = False
    else:
        msg = "Review did not end with ACCEPTED or REJECTED"
        raise ValueError(msg)

    return Review(accepted=accepted, text=review)
