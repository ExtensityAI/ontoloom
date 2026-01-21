from symai import Expression

from ontology_hydra.ontology.models import Ontology

# TODO: we want the model to update the ontology where it is most important, so maybe:
# 1) add a cleanup step after every few steps, where it just updates and moves around and improves stuff instead of adding?
# 2) have the model select a subtree and update that
# 3) the model often tries to update prop domain/range to include classes that are already included through subclass hierarchy

_prompt = """You are an ontology engineer extending an existing ontology to better capture a user's domain.

## Supported OWL Constructs

You can define classes as named concepts with optional subclass hierarchies, such as a Sensor class as a subclass of Device. Data properties attach literal values (string, int, float, boolean, datetime, date, time) to classes—for instance, a temperature property on Sensor with float range. Object properties link classes together, like a locatedIn property from Sensor to Location. You may also use class intersections in domains or ranges when a property applies only to entities satisfying multiple classes.

Do not use equivalentClass, subPropertyOf, inverseOf, cardinality restrictions, unions, complements, or individuals—these are not supported. Never mark anything as deprecated; instead, delete it outright or modify it to fit the new design.

## Current State

<intent>{intent}</intent>
<ontology>{ontology}</ontology>

## Task

Propose a focused set of changes that address one coherent aspect of the user's intent. Prefer depth over breadth—expand a specific area thoroughly rather than scattering additions across unrelated concepts. """


def draft_plan(intent: str, ontology: Ontology):
    """Drafts a plan that, when implemented and executed, changes the ontology to better fit user intent."""

    # if this does not work, well enough (low-quality plans), we may want to try to add in more steps to reiterate on the plan and provide more guidance maybe?

    # use raw prompting instead of structured output because we need flexibility and no data structure
    plan: str = Expression.prompt(
        _prompt.format(intent=intent, ontology=ontology.model_dump_json())
    ).value

    return plan
