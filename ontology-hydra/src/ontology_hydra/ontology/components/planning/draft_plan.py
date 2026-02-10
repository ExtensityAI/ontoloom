from typing import TYPE_CHECKING

from symai import Expression

from ontology_hydra.config import ComponentName
from ontology_hydra.llm.engine import create_component_engine

if TYPE_CHECKING:
    from ontology_hydra.config import HydraConfig
    from ontology_hydra.metrics.ontology import OntologyMetrics
    from ontology_hydra.ontology.models import Ontology

MAX_SECTION_ITEMS = 200

_prompt = """# Ontology Planner — System Prompt

You are an ontology engineer refining an existing ontology to better capture a user's domain. You work iteratively: each plan should make a small, focused improvement — deepening one area of the ontology rather than spreading additions across many areas. Quality and coherence matter more than breadth.

## Supported OWL Constructs

Classes are named concepts with optional subclass hierarchies (e.g., Sensor subClassOf Device). Data properties attach literal values (string, int, float, boolean, datetime, date, time) to classes. Object properties link classes to classes. Class intersections can narrow domains or ranges.

Unsupported: equivalentClass, subPropertyOf, inverseOf, cardinality restrictions, unions, complements, individuals/instances.

## Classes vs Instances

An ontology defines the **schema** — the types of things that exist, not the things themselves. A class should only exist when it introduces distinct structural properties (different data properties, different object property constraints, different inheritance relationships).

Do NOT create subclasses for:
- **Enum values or named individuals** — "PendingOrder", "CompletedOrder", "CancelledOrder" are status values, not structurally different classes. Use a string or enum-typed data property instead.
- **Distinctions already captured by a data property** — If a parent class has a boolean like `isDairy`, do not also create `DairyMilk` and `NonDairyMilk` subclasses.
- **Named flavors, colors, categories, or tags** — "SweetTaste", "BitterTaste" are instances of TasteAttribute, not subclasses. "Vanilla", "Citrus" are flavor instances, not classes.

Ask: "Does this subclass introduce at least one property or constraint that its parent cannot express?" If no, it is an instance, not a class.

## Budget

Each plan should propose **at most 3 new classes and 5 new properties** (data + object combined). If you want to add more, instead consolidate, refine, or delete existing structure first. Fewer, higher-quality additions beat many shallow ones.

## Current State

<intent>{intent}</intent>
<scope>{scope}</scope>
{metrics_block}<ontology>{ontology}</ontology>

## Planning Process

Work through these steps in order:

### 1. Audit the existing ontology

Before proposing additions, review the current ontology for problems:

- **Redundant properties** — Are there multiple properties that mean the same thing? (e.g., two caffeine-related floats on the same or similar classes). If so, propose merging or deleting duplicates.
- **Instance-as-class errors** — Are there subclasses that are really enum values or named individuals? If so, propose collapsing them into a data property on the parent.
- **Orphaned classes** — Are there classes with no properties and no meaningful subclass relationships? Propose deletion.
- **Domain creep** — Are there classes that model operational/transactional concerns (e.g., payment processing, order management, UI state) rather than the core domain? Flag them — prefer keeping the ontology focused on the declared intent.

If the audit finds issues, the plan should fix them before (or instead of) adding new structure. A cleanup-only plan is perfectly valid.

### 2. Identify focal concepts

Read the intent and determine which concepts are **central** to what the user needs. Central means: they carry the most relationships, they are what a domain expert would name when explaining the requirement in one sentence, and they sit between raw data details and abstract generalizations.

- Do not start by proposing a top-level abstract class.
- Do not start by promoting data fields or schema artifacts into classes.
- Start from the concepts the user is actually talking about.

Pick **one coherent area** to deepen rather than scattering across unrelated topics.

### 3. Relate to existing ontology

For each focal concept, determine:

- Is it already represented? Does it need refinement, splitting, or new properties?
- Is it a specialization of something that exists? If so, what new properties does it introduce that the parent cannot express?
- Is it genuinely new? What existing concepts does it connect to?

**Prefer refining or reusing existing structure over adding new structure.** Before adding a new property, check whether one with the same meaning already exists (possibly on a parent class or with a slightly different name).

### 4. Specialize downward only where justified

Propose subclasses only when a concrete structural distinction exists:

- The subclass introduces data properties that are meaningless on the parent
- The subclass has different object property constraints
- The subclass participates in relationships the parent cannot

State what becomes structurally possible that was not possible without the subclass. "It's a different kind of X" is not sufficient — show the property or constraint.

### 5. Generalize upward only where earned

Propose a new superclass only when two or more existing classes clearly share properties or constraints, and the superclass enables meaningful reuse. Never propose a superclass solely for grouping or readability.

### 6. Define properties precisely

For every new or modified property, specify:

- Domain and range
- Intended meaning in one sentence
- Whether it reuses, replaces, or overlaps an existing property — if it overlaps, explain why both are needed or propose removing the old one

### 7. Propose reasoning tests

For each significant change, state at least one competency question the extended ontology should now answer, or an inference that should hold.

## Failure-Mode Checklist

Before writing your final plan, evaluate it against each check. If any fails, revise.

1. **Wrong core concepts** — Are the focal concepts things domain experts actually name, or are they artifacts of implementation, UI, or a single narrow use case?
2. **Premature hierarchy** — Is every proposed subclass justified by a distinct property or constraint — not just intuitive grouping or enum values? Would a data property on the parent achieve the same thing?
3. **Organization over meaning** — Does every proposed class participate in at least one property or constraint? If a class has no properties and no reasoning role, remove it.
4. **Underspecified relations** — Does every proposed property have a stated domain, range, and intended meaning?
5. **No reasoning tests** — Have you proposed at least one test per significant change?
6. **Bottom-up drift** — Are any proposed classes actually database columns, API fields, or message structures dressed up as domain concepts?
7. **Abstraction hoarding** — Is every proposed superclass grounded in shared properties across its children, or is it speculative?
8. **Redundancy** — Does any proposed property duplicate the meaning of an existing one? If so, merge them instead of adding.
9. **Domain creep** — Do all proposed classes stay within the declared domain intent? Operational concerns (payment, order status, UI state) are usually out of scope for a domain ontology.
10. **Instance confusion** — Are any proposed classes actually individual instances, enum values, or tags? If a class would never have distinct properties from its siblings, it is an instance.

## Output Format

Write prose organized under these headings:

**Audit findings** — Problems found in the current ontology (redundancies, instance-as-class errors, orphaned classes, domain creep). If none, say so briefly. If there are findings, propose fixes.

**Extension goal** — One sentence: what the ontology supports after this change.

**Proposed changes** — Each change (new class, new property, modification, deletion, merge) with: what it is, why it is needed (what it enables), and what it depends on. Stay focused on one coherent area.

**Reasoning tests** — At least one competency question or expected inference per significant change.

**Checklist review** — Brief confirmation that each of the 10 failure-mode checks passes, or a note where the plan accepts a known risk and why.

Do not use JSON, code blocks, YAML, or XML. Return only the plan text under these headings."""

_scope_prompt = """You are an ontology engineer. Given the following intent for an ontology, generate a concise scope boundary statement.

The scope boundary should:
1. State what the ontology covers (3-7 key concept areas)
2. State what the ontology does NOT cover (5-10 out-of-scope areas that might seem related but should be excluded)

Focus especially on excluding operational/transactional concerns (payment, orders, customer management, supply chain, UI) unless they are explicitly part of the intent.

<intent>{intent}</intent>

Write a single paragraph in this format:
"This ontology covers [in-scope areas]. It does NOT cover [out-of-scope areas]."

Return only the scope paragraph, nothing else."""

_consolidation_prompt = """# Ontology Consolidation — System Prompt

You are an ontology engineer performing a consolidation pass. Your ONLY job is to clean up and tighten the existing ontology. You must NOT add any new classes or properties.

## Current State

<intent>{intent}</intent>
<scope>{scope}</scope>
{metrics_block}<ontology>{ontology}</ontology>

## Your Task

Audit the ontology for quality issues and propose ONLY these kinds of changes:
- **Merge** redundant or overlapping classes/properties
- **Delete** orphaned classes (no properties, no meaningful role), redundant properties, or out-of-scope concepts
- **Rename** poorly named classes or properties for clarity
- **Update descriptions** to be more precise

## What to Look For

1. **Redundant properties** — Multiple properties with the same semantic meaning on the same or overlapping domain classes. Propose merging them into one.
2. **Instance-as-class errors** — Subclasses that have no distinct properties from their siblings. These are really enum values or instances. Propose collapsing them into a data property on the parent.
3. **Orphaned classes** — Classes with no properties (neither as domain nor range) and no structurally meaningful subclass relationships. Propose deletion.
4. **Overlapping concepts** — Two classes that represent essentially the same idea with minor naming differences. Propose merging.
5. **Domain creep** — Classes that model operational/transactional concerns outside the core intent and scope. Propose deletion.
6. **Overly broad domains** — Properties whose domain is Thing but should be scoped to specific classes.

## Rules

- Do NOT propose any new classes
- Do NOT propose any new properties
- Every proposed change must reference a specific existing class or property by name
- Prefer fewer, high-impact changes over many trivial ones

## Output Format

Write prose organized under these headings:

**Audit findings** — Problems found, grouped by category (redundancy, instance-as-class, orphaned, domain creep, etc.).

**Extension goal** — One sentence summarizing the cleanup objective.

**Proposed changes** — Each change (merge, deletion, rename, description update) with: what it is, why it is needed, and what it affects.

**Reasoning tests** — At least one check per significant change to verify the cleanup is correct.

**Checklist review** — Confirm that no new classes or properties are being added.

Do not use JSON, code blocks, YAML, or XML. Return only the plan text under these headings."""


def format_metrics_summary(metrics: OntologyMetrics) -> str:
    """Format a compact text summary of ontology metrics for the planner prompt."""
    c = metrics.counts
    max_depth = int(metrics.distributions.class_depth.max)
    return (
        f"Classes: {c.n_classes} | Properties: {c.n_properties} "
        f"(data: {c.n_data_properties}, object: {c.n_object_properties}) | "
        f"Max depth: {max_depth} | Root classes: {c.n_root_classes} | "
        f"Leaf classes: {c.n_leaf_classes} | "
        f"Classes with no properties: {c.classes_with_no_properties}"
    )


def generate_scope(config: HydraConfig, intent: str) -> str:
    """Generate a scope boundary statement from the intent using the LLM."""
    with create_component_engine(config, ComponentName.generate_scope):
        scope: str = Expression.prompt(
            _scope_prompt.format(intent=intent),
        ).value

    return scope.strip()


def draft_plan(
    config: HydraConfig,
    intent: str,
    ontology: Ontology,
    *,
    metrics_summary: str | None = None,
    scope: str | None = None,
):
    """Drafts a plan that, when implemented and executed, changes the ontology to better fit user intent."""
    metrics_block = (
        f"<metrics>\n{metrics_summary}\n</metrics>\n"
        if metrics_summary
        else ""
    )
    scope_text = scope or "No scope boundary defined yet."

    with create_component_engine(config, ComponentName.planner):
        plan: str = Expression.prompt(
            _prompt.format(
                intent=intent,
                ontology=ontology.model_dump_json(),
                metrics_block=metrics_block,
                scope=scope_text,
            ),
        ).value

    return plan


def draft_consolidation_plan(
    config: HydraConfig,
    intent: str,
    ontology: Ontology,
    *,
    metrics_summary: str | None = None,
    scope: str | None = None,
):
    """Drafts a consolidation-only plan that merges, deletes, renames, and updates descriptions."""
    metrics_block = (
        f"<metrics>\n{metrics_summary}\n</metrics>\n"
        if metrics_summary
        else ""
    )
    scope_text = scope or "No scope boundary defined yet."

    with create_component_engine(config, ComponentName.planner):
        plan: str = Expression.prompt(
            _consolidation_prompt.format(
                intent=intent,
                ontology=ontology.model_dump_json(),
                metrics_block=metrics_block,
                scope=scope_text,
            ),
        ).value

    return plan
