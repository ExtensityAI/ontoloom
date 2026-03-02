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

This makes diagnostics extensible: adding a new check with a richer hint is equivalent to adding a new "skill" — no code changes needed beyond the detection logic. See [CATALOG.md](CATALOG.md) for the full hint for each diagnostic. Where a diagnostic maps to an established ontology design pattern, the hint references the pattern template — see [PATTERNS.md](PATTERNS.md).

### Dispatch Context

When delegating to a resolution subagent, the system provides:

1. **Finding** — the specific diagnostic finding with affected entities
2. **Hint** — from the catalog
3. **Entity context** — the affected entities' descriptions, properties, hierarchy position, and 1-hop neighbors
4. **Decision registry entries** — relevant global and per-entity decisions
5. **Scope constraint** — what area the fix should stay within

---

## Batching Strategy

Findings are batched per-subtree and per-category within the subtree. Batch size: 3–8 findings — enough for the subagent to see interactions, small enough for the main agent to review coherently.

| Batch | Findings | Rationale |
|---|---|---|
| SubClassOf pair review | T01, T02, T03, T04, T10, T13 | All examine parent-child relationships |
| Sibling group review | T07, T09, T11, T14, T15 | All examine sibling sets |
| Property review | P01–P18, DT01–DT06 | All examine property modeling |
| Expansion review | S05, S08, T12, M01–M10, coverage gaps | All produce additive fixes |
| Naming batch | N01–N11, CC01–CC04 | Mechanical, can be batched aggressively |

Within each batch, the subagent sees all findings in the batch simultaneously and can produce proposals that account for interactions (e.g., fixing T01 on one entity may resolve T13 on a sibling). Coherent proposals that span taxonomy and property changes (e.g., reclassifying a class and updating its properties in one proposal) are encouraged when the changes form a natural unit of work.

---

## Fix Ordering

Findings are resolved in three **phases**. Phase boundaries are hard gates; ordering within a phase is a heuristic default based on blast radius.

The original design used four tiers (structure → taxonomy → properties → naming) with a strict unidirectional dependency chain. This was revised after literature review showed the taxonomy-to-property dependency is **bidirectional** — property analysis informs taxonomy decisions (OntoClean metaproperties, property signature similarity), not just the reverse. Additionally, moving a class in the hierarchy does not break property references (properties reference classes by name, which survives reparenting). The 3-phase system merges taxonomy and property work, reducing round count and eliminating the need for cross-phase escalation.

### Phase 1 — Foundation (fix first)

Fixes that reshape the top-level class hierarchy or address scope alignment. Everything below may need re-evaluation.

- **T14:** umbrella classes at top levels
- **T06:** flat taxonomy
- **S03:** fan-out hotspots at top levels
- **S01:** disconnected components (do these classes belong?)
- **IA01/IA02:** domain mismatch, scope creep (remove before fixing)
- **ML01:** meta-level contamination
- **D1.4:** dangling class references
- Exploration findings about top-level organization

**After Phase 1:** Full re-diagnosis. The graph may have changed fundamentally. Phase 1 → 2 is a **hard gate** — all subtrees must pass before any subtree enters Phase 2.

### Phase 2 — Modeling (fix second)

All taxonomy, property, and expansion work. Processes per-subtree, ordered by blast radius within each subtree. Taxonomy and property findings are addressed together, with reclassification changes taking priority.

**Taxonomy semantics:**
- **T01–T04:** is-a overloading (subClassOf → partOf, hasRole, etc.)
- **T05:** instances as classes (move to ABox)
- **T07:** miscellaneous/catch-all classes
- **T09:** polysemous concepts (split)
- **T10:** surface-name taxonomy
- **T11:** temporal-atemporal conflation
- **T13:** abstraction level mixing
- **T15:** epistemic intrusion
- **T16:** category vs. class confusion

**Property structure:**
- **P01:** multiple domain/range intersection trap
- **P03:** missing domain/range
- **P05:** over-specialized domain/range
- **P11:** redundant per-class properties
- **P12:** flat property hierarchy
- **P13–P18:** inverse checks, sub-property checks, consolidation

**Expansion:**
- **S05/S08:** empty shells, property deserts (additive fixes)
- **T12:** granularity mismatch (additive fixes)
- **M01–M10:** modeling pattern violations
- **DT01–DT06:** datatype issues
- Coverage gaps from exploration and document analysis

**After Phase 2:** Re-diagnose affected subtrees. Per-subtree advancement — clean subtrees proceed independently.

### Phase 3 — Polish (fix last)

No structural impact. Safe to batch and auto-fix where possible.

- **N01–N11:** casing, plurals, labels, annotations
- **A01–A07:** documentation, provenance
- **D01:** redundant subClassOf (cleanup)
- **CC01–CC04:** cross-cutting concern naming patterns
- **D3.9:** sparse descriptions

**After Phase 3:** No re-diagnosis needed.

### Ordering Within Phase 2

Within a subtree, findings are ordered by three criteria:

1. **Blast radius.** Reclassification (T01–T04, T09, T13 — these move classes around) before structural additions (T12, S05 — adding intermediate classes) before property adjustments (P01–P18 — domain/range changes). This is a **heuristic default**, not a hard gate — coherent proposals that span taxonomy and property changes are encouraged when they form a natural unit of work.
2. **Hierarchy depth.** A warning at depth 1 before a critical at depth 3. A depth-1 fix has larger blast radius and may resolve the depth-3 finding as a side effect.
3. **Severity.** Within the same blast radius class and depth.

Reversible changes before entangling ones, as before: removals (scope trimming, orphan removal) before additions before deep restructuring.

### Per-Subtree Advancement

Phase 2 processes per-subtree. A subtree whose findings are all resolved can be marked clean while other subtrees continue work. This prevents one problematic branch from blocking progress across the entire ontology.

Phase 1 → 2 is **global** (hard gate). Phase 2 → 3 is effectively global in practice — Phase 3 starts when all subtrees have completed Phase 2, since naming/annotation fixes can't interact with ongoing modeling work in a meaningful way.

### Phase Assignment Heuristic

- Does fixing this change top-level structure or scope alignment? → Phase 1
- Does it change taxonomy, property structure, or add content? → Phase 2
- Is it purely cosmetic (naming, annotations, redundancy cleanup)? → Phase 3

---

## Re-Diagnosis Scope

Each phase specifies how much of the ontology needs re-diagnosis after fixes are applied:

| Phase | Re-diagnosis scope | Rationale |
|---|---|---|
| Phase 1 | Full re-diagnosis (all passes) | Graph may have changed fundamentally |
| Phase 2 | Re-diagnose affected subtrees | Modeling changes are subtree-local |
| Phase 3 | None | Naming/cosmetic changes have no structural impact |

---

## Auto-Fix

Some findings have mechanical fixes that don't require LLM judgment. These are applied silently in the auto-fix pass (step 2 of the round), before exploration:

- **N01:** re-case to convention (PascalCase classes, camelCase properties)
- **D01:** remove redundant subClassOf (transitive reduction)
- **N09:** simplify path-containing labels
- **N11:** swap label/comment when label is longer
- **A04:** trim whitespace
- **M09:** replace "is"/"isA" property with OWL primitive

Auto-fixes are reported in the progress report ("12 naming violations auto-fixed") but not routed through the main agent for approval. See [CATALOG.md](CATALOG.md) for the complete list.

**Note:** N02 (singularize plural names) was removed from auto-fix due to unreliable accuracy on domain-specific vocabulary (documented error rates of 15–50% on technical terms). It now uses flag-and-propose via the exploration pass. See [CATALOG.md](CATALOG.md) § N02 for details.

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

Every finding must be resolved — pick an option, request more exploration, or explicitly defer. No finding is silently ignored. See [ARCHITECTURE.md](ARCHITECTURE.md) § Decision Registry § Force-Resolution for details.

---

## Open Design Questions

1. **Resolution batching granularity.** One LLM call per finding vs. per category vs. per subtree. Deferred to implementation — will depend on observed cost and quality tradeoffs.

2. **Diff application order.** When multiple proposals in the same batch produce diffs, should they be applied sequentially (checking for conflicts) or merged into one atomic batch? Sequential is safer; batched is faster.
