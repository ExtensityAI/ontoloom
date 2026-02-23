# Bootstrap Phase

The bootstrap phase is the structured first phase before the main diagnose/resolve loop. It captures the user's intent, establishes scope, and produces the initial ontology seed.

For overall lifecycle, see [ARCHITECTURE.md](ARCHITECTURE.md) § Lifecycle. For the prompt template used during bootstrap, see [PROMPTING.md](PROMPTING.md) § Bootstrap Turn.

---

## Purpose

The bootstrap captures initial direction so the system can begin generating. The user is NOT expected to know everything upfront — the scope document grows organically as the system encounters ambiguity during the main loop.

### What Bootstrap Produces

1. **Scope document** — the drift anchor (see § Scope Document below)
2. **Initial ontology** — a minimal seed, not a comprehensive draft
3. **User alignment** — the system and user have a shared understanding of what's being built

---

## Bootstrap Flow

### Step 1: Understand Intent

The system receives the user's intent (e.g., "an ontology for IoT sensor networks") and reflects it back:

- What domain is this?
- What are the major concept areas?
- What's the likely purpose (querying, classification, data integration)?

### Step 2: Ask Scoping Questions

2–3 questions to understand:

- **What to represent** — what data, entities, relationships matter?
- **What questions to answer** — what queries should the ontology support? (Competency-style questions as soft guidance, not a hard spec.)
- **What's out of scope** — what should the ontology deliberately *not* model?

Questions are framed in plain language. The user is not an ontology engineer. No OWL jargon.

**Good:** "Should the ontology track where sensors are physically mounted, or just what they measure?"
**Bad:** "Should we model hasLocation as a transitive object property with domain Sensor?"

### Step 3: Seed the Scope Document

The system creates the scope document from what it learned — the user's goals, initial include/exclude decisions, and any design principles that emerged.

### Step 4: Generate Initial Ontology

Using its ontology modeling expertise, the system generates an initial seed covering the major concept areas. The seed is:

- **Minimal** — just enough structure to start the diagnostic loop
- **Informed by intent** — not generic; reflects the user's domain
- **Imperfect on purpose** — the diagnostic loop will refine it

The ontology starts from `Thing` and builds top-level classes with initial properties. The first diagnostic round will identify everything that's wrong or missing.

---

## Scope Document

The scope document is the system's drift anchor — the accumulated understanding of what's in scope, what's out, and why. It persists across all diagnostic rounds.

### Format

```markdown
## User Goals
- [Original user request — never modified]

## Decided Scope
### [Domain Area]
- Include: ...
- Exclude: ... (user decision, round N)
- Granularity: ...

### [Domain Area]
- [pending user decision on ...]

## Design Principles
- [Principle] (source: user/system, round N)
```

### Rules

- The scope document is **never summarized or compacted.** Always included in full.
- Each entry records **provenance** — which round, user or system decision.
- Soft guidance, not hard boundaries. The system can deviate if it explains why.
- The user can correct it at any time.
- Grows organically as the system encounters ambiguity.

### Scope Echo

The scope document sits at the top of prompt context (primacy bias). The prompt instructions additionally echo the 2–3 most important scope constraints at the bottom (recency bias). This double-anchoring — top and bottom — is the strongest anti-drift measure available.

The echo is extracted automatically: pick the top entries from "Decided Scope" (exclude/include decisions) and "Design Principles." Keep it under ~50 tokens.

Based on research: simple reminder interventions reliably reduce goal divergence ("Drift No More," Oct 2025).

---

## User Interaction

### When to Ask the User

The system surfaces questions when it encounters genuine modeling ambiguity that depends on the user's domain knowledge or preferences:

- **Scope boundaries** — "The ontology includes Aircraft. Should it also cover ground support equipment (fuel trucks, baggage carts)?"
- **Modeling philosophy** — "Employees can be managers. Should Manager be a separate class, or a role that any Employee can have?"
- **Granularity** — "How detailed should the sensor hierarchy be? Just sensor types (temperature, pressure), or also specific models?"

### How to Frame Questions

Questions must be understandable by someone who knows the domain but not OWL:

| Concept | Plain language | Not this |
|---|---|---|
| subClassOf vs. role | "Should X be a type of Y, or a role that Y can have?" | "Should X be modeled as anti-rigid per OntoClean?" |
| partOf vs. is-a | "Is X a component of Y, or a kind of Y?" | "Should we use mereological vs. taxonomic relations?" |
| Granularity | "How detailed should this area be?" | "What's the target depth for this subtree?" |
| Scope | "Should the ontology include X?" | "Should we expand the domain closure to include X?" |

### Non-Blocking Questions

In interactive mode, questions don't block the system. The system continues working on other areas and incorporates answers when they arrive. This prevents the system from stalling while waiting for user input.

---

## Stopping Conditions

The system considers the ontology complete when:

1. **All tiers clean or explicitly deferred** — every diagnostic finding is either fixed or deferred with reasoning in the decision registry.
2. **Decision review** — all deferred decisions are reconsidered against the completed ontology. Decisions made early (when the ontology was small) may now be addressable.
3. **Self-review** — a final holistic check against the scope document. Does the ontology coherently cover the stated intent?

These conditions are checked by the system, not described to the agent mechanically. The agent is told to finish "when you believe the ontology covers the intent well." The system validates silently. If conditions aren't met, the rejection explains what's wrong. This avoids giving the agent a perverse incentive to game the conditions (e.g., deferring everything to reach "all clean").

---

## Example Bootstrap

**User intent:** "An ontology for a university course management system"

**System reflection:**
"This is an academic/education domain. Major concept areas: people (students, faculty, staff), courses and programs, facilities, scheduling. Purpose is likely data integration and querying."

**Scoping questions:**
1. "Should the ontology cover just courses and enrollment, or also facilities (rooms, buildings) and scheduling (time slots, semesters)?"
2. "How should we handle people who have multiple roles — for example, a graduate student who also teaches? Should each role be a separate type, or should the same person have multiple roles?"
3. "Should the ontology include research (labs, publications, grants) or focus purely on teaching and courses?"

**Initial scope document:**
```markdown
## User Goals
- An ontology for a university course management system

## Decided Scope
### People
- Include: students, faculty, staff
- [pending: role modeling approach — waiting for user answer on Q2]

### Courses
- Include: courses, programs, departments
- Granularity: course level (not individual lectures/sessions)

### Facilities & Scheduling
- [pending user decision on Q1]

### Research
- [pending user decision on Q3]

## Design Principles
- (none yet)
```

**Initial ontology seed:** Top-level classes for Person, Course, Department, Program with basic properties. The diagnostic loop will identify what's missing (property deserts, flat hierarchy, coverage gaps) and drive expansion.
