from symai import Expression

from ontology_hydra.ontology.models import Ontology

# TODO: prompt the model with the subset of OWL that we are supporting! remind it of key principles! locality of edit?
# TODO: what if data does not fit user intent? model needs to be able to skip this?

_prompt = """You are an ontology engineer extending an existing ontology to better capture a user's domain.

<intent>{intent}</intent>
<data>{data}</data>
<ontology>{ontology}</ontology>

Analyze the gap between the current ontology and what's needed to represent the sample data according to the user's intent. Then describe each proposed change in a short paragraph:
- State the modification (e.g., "Add a Property class with attributes for price and location")
- Explain what information from the data this captures (quote specific phrases or values)
- Clarify how this improves the ontology's ability to model the domain

Write prose, not tables or bullet lists. Be specific and grounded in the data."""


def draft_plan(intent: str, data: str, ontology: Ontology):
    """Drafts a plan that, when implemented and executed, changes the ontology to better fit user intent and sample data."""

    # if this does not work, well enough (low-quality plans), we may want to try to add in more steps to reiterate on the plan and provide more guidance maybe?

    # use raw prompting instead of structured output because we need flexibility and no data structure
    plan: str = Expression.prompt(
        _prompt.format(intent=intent, data=data, ontology=ontology.model_dump_json())
    ).value

    return plan
