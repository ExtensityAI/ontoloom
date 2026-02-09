from symai import Expression

from ontology_hydra.config import ComponentName, HydraConfig
from ontology_hydra.llm.engine import create_component_engine
from ontology_hydra.ontology.models import ClassExpression, IntersectionOf, Ontology

# TODO: we want the model to update the ontology where it is most important, so maybe:
# 1) add a cleanup step after every few steps, where it just updates and moves around and improves stuff instead of adding?
# 2) have the model select a subtree and update that
# 3) the model often tries to update prop domain/range to include classes that are already included through subclass hierarchy

MAX_SECTION_ITEMS = 200

_prompt = """You are an ontology engineer extending an existing ontology to better capture a user's domain.

## Supported OWL Constructs

You can define classes as named concepts with optional subclass hierarchies, such as a Sensor class as a subclass of Device. Data properties attach literal values (string, int, float, boolean, datetime, date, time) to classes—for instance, a temperature property on Sensor with float range. Object properties link classes together, like a locatedIn property from Sensor to Location. You may also use class intersections in domains or ranges when a property applies only to entities satisfying multiple classes.

Do not use equivalentClass, subPropertyOf, inverseOf, cardinality restrictions, unions, complements, or individuals—these are not supported. Never mark anything as deprecated; instead, delete it outright or modify it to fit the new design.

## Current State

<intent>{intent}</intent>
<ontology>{ontology}</ontology>

## Task

Propose a focused set of changes that address one coherent aspect of the user's intent. Prefer depth
over breadth—expand a specific area thoroughly rather than scattering additions across unrelated
concepts.

## Output Format

Write prose. Do not use JSON. Do not use code
blocks, YAML, or XML. Return only the plan text."""


def _format_class_expression(expr: ClassExpression) -> str:
    if isinstance(expr, IntersectionOf):
        return " AND ".join(expr.classes)

    return str(expr)


def _format_class_expressions(exprs: list[ClassExpression]) -> str:
    if not exprs:
        return "none"

    return ", ".join(_format_class_expression(expr) for expr in exprs)


def _format_ontology(ontology: Ontology) -> str:
    lines = ["Classes:"]
    class_names = sorted(ontology.classes)
    for name in class_names[:MAX_SECTION_ITEMS]:
        class_def = ontology.classes[name]
        description = class_def.description.definition
        constraints = class_def.description.constraints
        parents = _format_class_expressions(class_def.sub_class_of)
        if constraints:
            lines.append(f"{name}: {description} Constraints: {constraints} Parents: {parents}.")
        else:
            lines.append(f"{name}: {description} Parents: {parents}.")

    remaining_classes = len(class_names) - MAX_SECTION_ITEMS
    if remaining_classes > 0:
        lines.append(f"... and {remaining_classes} more classes.")

    lines.append("Data properties:")
    data_property_names = sorted(ontology.data_properties)
    for name in data_property_names[:MAX_SECTION_ITEMS]:
        prop = ontology.data_properties[name]
        description = prop.description.definition
        constraints = prop.description.constraints
        domain = _format_class_expressions(prop.domain)
        if constraints:
            lines.append(
                f"{name}: {description} Constraints: {constraints} Domain: {domain}. "
                f"Range: {prop.range.value}.",
            )
        else:
            lines.append(f"{name}: {description} Domain: {domain}. Range: {prop.range.value}.")

    remaining_data_properties = len(data_property_names) - MAX_SECTION_ITEMS
    if remaining_data_properties > 0:
        lines.append(f"... and {remaining_data_properties} more data properties.")

    lines.append("Object properties:")
    object_property_names = sorted(ontology.object_properties)
    for name in object_property_names[:MAX_SECTION_ITEMS]:
        prop = ontology.object_properties[name]
        description = prop.description.definition
        constraints = prop.description.constraints
        domain = _format_class_expressions(prop.domain)
        range_classes = _format_class_expressions(prop.range)
        if constraints:
            lines.append(
                f"{name}: {description} Constraints: {constraints} Domain: {domain}. "
                f"Range: {range_classes}.",
            )
        else:
            lines.append(f"{name}: {description} Domain: {domain}. Range: {range_classes}.")

    remaining_object_properties = len(object_property_names) - MAX_SECTION_ITEMS
    if remaining_object_properties > 0:
        lines.append(f"... and {remaining_object_properties} more object properties.")

    return "\n".join(lines)


def draft_plan(config: HydraConfig, intent: str, ontology: Ontology):
    """Drafts a plan that, when implemented and executed, changes the ontology to better fit user intent."""

    # if this does not work, well enough (low-quality plans), we may want to try to add in more steps to reiterate on the plan and provide more guidance maybe?

    # use raw prompting instead of structured output because we need flexibility and no data structure
    with create_component_engine(config, ComponentName.planner):
        plan: str = Expression.prompt(
            _prompt.format(intent=intent, ontology=_format_ontology(ontology)),
        ).value

    return plan
