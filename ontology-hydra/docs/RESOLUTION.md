# Resolution Pass

The resolution pass is the third of three passes in each diagnostic round. It takes findings from the deterministic and exploration passes and produces concrete fix proposals with 2–3 options each.

For how this fits into the round structure, see [ARCHITECTURE.md](ARCHITECTURE.md) § Round Structure. For the upstream passes, see [CATALOG.md](CATALOG.md) (deterministic) and [EXPLORATION.md](EXPLORATION.md) (exploration).

---

## Purpose

Findings describe *what's wrong*. The resolution pass produces *how to fix it* — concrete, actionable proposals with diffs against the ontology model. The main agent then reviews proposals and makes decisions.

**Input:** All findings (deterministic + exploration), decision registry.
**Output:** Proposals with 2–3 fix options each, including concrete diffs.
**Cost:** ~1 LLM call per finding, or batched by category.

---

## Proposal Generation

For each finding, a resolution subagent:

1. Considers the finding in context (affected entities, their neighborhood, registry decisions)
2. Proposes 2–3 fix options with concrete diffs against the ontology model
3. Notes tradeoffs for each option

### Proposal Structure

```
Proposal:
  finding: S03 — fan-out hotspot on Vehicle (25 direct subclasses)
  options:
    1. Introduce grouping classes by function (GroundVehicle, AerialVehicle, WaterVehicle)
       diff: add 3 classes, move 25 subclasses under them
       tradeoffs: +cleaner hierarchy, +navigability; -adds a level of indirection
    2. Introduce grouping classes by use case (PassengerVehicle, CommercialVehicle, EmergencyVehicle)
       diff: add 3 classes, move 25 subclasses under them
       tradeoffs: +aligns with user domain (fleet management); -some vehicles fit multiple categories
    3. Keep current structure, defer with reasoning
       diff: none
       tradeoffs: +no structural change; -25 siblings remains hard to navigate
```

Each option's `diff` is a concrete list of mutation operations (see § Mutation API below).

---

## Hints as Skills

Each diagnostic in the catalog includes a **hint** — guidance for investigating or fixing the issue. Hints range from short ("rename to PascalCase") to detailed procedures. The resolution subagent reads the hint and uses it as a starting point for generating proposals.

This makes diagnostics extensible: adding a new check with a richer hint is equivalent to adding a new "skill" — no code changes needed beyond the detection logic. See [CATALOG.md](CATALOG.md) for the full hint for each diagnostic.

### Dispatch Context

When delegating to a resolution subagent, the system provides:

1. **Finding** — the specific diagnostic finding with affected entities
2. **Hint** — from the catalog
3. **Entity context** — the affected entities' descriptions, properties, hierarchy position, and 1-hop neighbors
4. **Decision registry entries** — relevant global and per-entity decisions
5. **Scope constraint** — what area the fix should stay within

---

## Batching Strategy

To reduce LLM calls, findings are batched by category:

| Batch | Findings | Rationale |
|---|---|---|
| SubClassOf pair review | T01, T02, T03, T04, T10, T13 | All examine parent-child relationships |
| Sibling group review | T07, T09, T11, T14, T15 | All examine sibling sets |
| Property review | P05, P09, P16, N07 | All examine property modeling |
| Expansion review | S05, S08, T12, coverage gaps | All produce additive fixes |
| Naming batch | N01–N11 | Mechanical, can be batched aggressively |

Within each batch, the subagent sees all findings in the batch simultaneously and can produce proposals that account for interactions (e.g., fixing T01 on one entity may resolve T13 on a sibling).

---

## Fix Ordering

Findings are resolved in order of **structural blast radius, top-down.** A fix at the root can cascade across the entire ontology. A naming fix at a leaf affects nothing.

### Tier 1 — Top-Level Structure (fix first)

Fixes that reshape the class hierarchy. Everything below may need re-evaluation.

- **T14:** umbrella classes at top levels
- **T06:** flat taxonomy
- **S03:** fan-out hotspots at top levels
- **S01:** disconnected components (do these classes belong?)
- **IA01/IA02:** domain mismatch, scope creep (remove before fixing)
- Exploration findings about top-level organization

**After tier 1:** Full re-diagnosis. The graph may have changed fundamentally.

### Tier 2 — Taxonomy Semantics (fix second)

Fixes that change what classes *are* — reclassification, splitting, merging. These move entities, change edges, alter graph topology.

- **T01–T04:** is-a overloading (subClassOf → partOf, hasRole, etc.)
- **T10:** surface-name taxonomy
- **T05:** instances as classes (move to ABox)
- **T09:** polysemous concepts (split)
- **T13:** abstraction level mixing

**After tier 2:** Re-diagnose affected subtrees.

### Tier 3 — Property Structure and Expansion (fix third)

The class hierarchy is now stable. Fix property modeling and fill gaps.

- **P01:** multiple domain/range intersection trap
- **P03:** missing domain/range
- **P05:** over-specialized domain/range
- **P11:** redundant per-class properties
- **S05/S08:** empty shells, property deserts (additive fixes)
- **T12:** granularity mismatch (additive fixes)
- Coverage gaps from exploration (additive fixes)

**After tier 3:** Re-check properties locally.

### Tier 4 — Naming and Cosmetics (fix last)

No structural impact. Safe to batch and auto-fix where possible.

- **N01–N11:** casing, plurals, labels, annotations
- **A01–A07:** documentation, provenance
- **D01:** redundant subClassOf (cleanup)
- **CC01–CC04:** cross-cutting concern naming patterns

**After tier 4:** No re-diagnosis needed.

### Ordering Within a Tier

**Higher in hierarchy first, then by severity.** A warning at depth 1 before a critical at depth 3. The rationale: a depth-1 fix has larger blast radius and may resolve the depth-3 finding as a side effect.

### Tier Assignment Heuristic

- Does fixing this change the subClassOf graph topology? → Tier 1–2
- Does it change property structure (domain/range/inverse)? → Tier 3
- Neither? → Tier 4

Some findings span tiers. T08 (missing disjointness) is taxonomy-adjacent but *adds* axioms rather than restructuring — tier 3, not tier 2. S13 (collapsible linear chain) changes structure but is very local — tier 2 but low priority within it. Assign by blast radius of the fix, not by catalog category.

---

## Re-Diagnosis Scope

Each tier specifies how much of the ontology needs re-diagnosis after fixes are applied:

| Tier | Re-diagnosis scope | Rationale |
|---|---|---|
| Tier 1 | Full re-diagnosis (all passes) | Graph may have changed fundamentally |
| Tier 2 | Re-diagnose affected subtrees | Taxonomy changes are subtree-local |
| Tier 3 | Re-check properties locally | Property changes don't affect hierarchy |
| Tier 4 | None | Naming changes have no structural impact |

---

## Auto-Fix

Some findings have mechanical fixes that don't require LLM judgment. These are applied silently in the auto-fix pass (step 2 of the round), before exploration:

- **N01:** re-case to convention (PascalCase classes, camelCase properties)
- **N02:** singularize plural class names
- **P07:** self-inverse → symmetric
- **P08:** remove redundant inverse on symmetric property
- **D01:** remove redundant subClassOf (transitive reduction)
- **D02:** remove redundant subClassOf alongside equivalentClass
- **N09:** simplify path-containing labels
- **N11:** swap label/comment when label is longer
- **A04:** trim whitespace
- **M09:** replace "is"/"isA" property with OWL primitive

Auto-fixes are reported in the progress report ("12 naming violations auto-fixed") but not routed through the main agent for approval. See [CATALOG.md](CATALOG.md) for the complete list.

---

## Mutation API

All fixes are expressed as sequences of atomic mutation operations. Each operation does one thing, returns success/failure + what changed. Validation is **eager** — invalid operations are rejected with an error explaining why.

### Class Operations

| Operation | Parameters | Notes |
|---|---|---|
| `add_class` | name, description, parents | Fails if name already exists |
| `delete_class` | name | Cascades: removes from all property domains/ranges, other classes' sub_class_of. Diff shows all cascaded changes. |
| `rename_class` | name, new_name | Atomic: cascades to all references (properties, sub_class_of) |
| `update_class_description` | name, description | |
| `move_class` | name, new_parents | Replaces sub_class_of list |

### Data Property Operations

| Operation | Parameters | Notes |
|---|---|---|
| `add_data_property` | name, description, domain, range | |
| `delete_data_property` | name | Diff shows what was removed |
| `rename_data_property` | name, new_name | Atomic cascade |
| `update_data_property_description` | name, description | |
| `set_data_property_domain` | name, domain | Replaces domain list |
| `set_data_property_range` | name, range | Changes the DataType |

### Object Property Operations

| Operation | Parameters | Notes |
|---|---|---|
| `add_object_property` | name, description, domain, range | |
| `delete_object_property` | name | Diff shows what was removed |
| `rename_object_property` | name, new_name | Atomic cascade |
| `update_object_property_description` | name, description | |
| `set_object_property_domain` | name, domain | Replaces domain list |
| `set_object_property_range` | name, range | Replaces range list |

### Composite Operations

| Operation | Parameters | Notes |
|---|---|---|
| `merge_classes` | source_classes, target_name, description | Unions properties, updates all references, removes sources |

More composites can be added if the LLM consistently fumbles specific multi-step sequences (e.g., `convert_class_to_data_property`, `split_class`).

### Diff Returns

Each mutation operation returns a **diff view** showing exactly what changed:
- Entities added/removed/modified
- References updated (cascaded changes)
- Validation warnings (if any)

This gives immediate feedback and makes the proposal's impact concrete.

---

## Force-Resolution

Every finding must be resolved. No finding is silently ignored. The main agent must:

1. **Pick an option** → decision stored in registry, diff queued for application
2. **Request more exploration** → exploration subagent investigates further, then resolution retries
3. **Explicitly defer** → decision stored with reasoning (won't be re-raised unless entities change)

This ensures the decision registry fills up, making each subsequent round smarter. Deferred decisions are reviewed before the system declares the ontology complete (see [ARCHITECTURE.md](ARCHITECTURE.md) § Lifecycle § Phase 3).

---

## Open Design Questions

1. **Resolution batching granularity.** One LLM call per finding vs. per category vs. per subtree. Deferred to implementation — will depend on observed cost and quality tradeoffs.

2. **Diff application order.** When multiple proposals in the same tier produce diffs, should they be applied sequentially (checking for conflicts) or merged into one atomic batch? Sequential is safer; batched is faster.
