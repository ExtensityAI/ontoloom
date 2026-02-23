# Diagnostics System Architecture

> Self-contained architecture doc for the ontology diagnostics system.
> Based on design discussion 2026-02-23.

---

## Overview

The diagnostics system is the core quality loop for ontology generation. It replaces the traditional agent loop (plan → draft → review → revise) with a simpler model:

```
initial draft → diagnose/resolve → diagnose/resolve → ... → clean
```

There is no separate "expansion" phase. Expansion is an emergent property of fixing incompleteness diagnostics — when a finding says "this branch is under-modeled," the fix is to add content. Correction and expansion flow through the same pipeline.

---

## Scope

The system operates on the current `Ontology` model:

- `owl:Class` + `rdfs:subClassOf`
- `owl:ObjectProperty` + `owl:DatatypeProperty`
- `rdfs:domain` + `rdfs:range`
- `rdfs:subPropertyOf`
- `owl:inverseOf`

**Explicitly out of scope (for now):**
- Restrictions (someValuesFrom, allValuesFrom, cardinality)
- Equivalence class definitions
- IntersectionOf / UnionOf
- Property characteristics (functional, symmetric, transitive)
- Disjointness axioms
- Embedding-based checks (deferred)
- Reasoner-based checks (lowest priority, may never be needed)

A single meta-diagnostic reports: "this ontology is purely taxonomic — no restrictions, no defined classes, no disjointness." This captures the absence of axioms as one info-level finding.

This scope covers ~55–60% of the full diagnostic catalog (DIAGS.md), targeting the highest-value checks for LLM-generated ontologies.

---

## Core Data Model

### Finding

What's wrong (or missing). Produced by deterministic checks or the exploration pass.

- **diagnostic_id** — catalog reference (e.g., "S03", "T01") or "EXP" for exploration findings
- **severity** — critical / warning / info
- **affected_entities** — list of class/property names involved
- **description** — human-readable explanation of the problem
- **tier** — fix ordering tier (1–4, see Fix Ordering)

### Proposal

A finding with concrete fix options. Produced by the resolution pass.

- **finding** — the underlying finding
- **options** — 2–3 fix alternatives, each with:
  - **description** — what this option does
  - **diff** — concrete modification to the ontology model
  - **tradeoffs** — what you gain/lose

### Decision

The main agent's response to a proposal. Stored in the registry.

- **proposal** — what was proposed
- **chosen_option** — which fix was selected (or "defer")
- **reasoning** — why this choice was made
- **scope** — global (applies everywhere) or local (applies to specific entities)

---

## Stateful Session

A `DiagnosticSession` is created per generation session and holds all state. It is not persisted across sessions.

### State Components

**Entity content hashes** — hash of each entity's semantically relevant fields (name, subClassOf, domain, range, etc.). Used to compute diffs between rounds. Field-level granularity — any field change marks the entity as changed.

**LLM judgment cache** — `(diagnostic_id, entity_content_hash)` → judgment result. If the entity hasn't changed, reuse the cached judgment. Invalidated when the entity or any 1-hop neighbor changes.

**Embedding cache** — `(entity_name, entity_definition_hash)` → vector. Only embed new/changed entities. Deferred but the slot exists in the design.

**Metrics history** — per-round snapshots of graph metrics (depth, fan-out distribution, modularity, etc.). Enables progress reporting: "modularity improved from 0.2 to 0.4."

**Decision registry** — the accumulated decisions from all prior rounds:
- **Global decisions:** Pattern-level choices that apply everywhere. "We model roles as separate classes with hasRole properties." "We use singular UpperCamelCase for all class names."
- **Per-entity decisions:** "Vehicle: 15 direct subclasses is intentional — they have distinct property signatures." "Student: modeled as role, not subclass of Person."

The registry is consulted before raising findings. If a finding was already resolved (fixed or explicitly deferred with reasoning), it is not re-raised unless the relevant entities changed.

**Previous ontology snapshot** — the full ontology from the prior round. Used with entity hashes to compute the change set.

### Incremental Re-diagnosis

On rounds after the first:

1. Diff current ontology against previous snapshot → `ChangedEntities`
2. Compute dirty set: changed entities + their 1-hop graph neighbors
3. **Entity-local checks** (N01, P03, R01): re-check only dirty set
4. **Neighborhood checks** (T08, S03, T01–T04): re-check only dirty set
5. **Global checks** (S01, S07, S14, IT metrics): always re-run (cheap — networkx on <500 nodes)
6. **Exploration pass**: only re-explore subtrees containing modified entities
7. Diff findings against previous round → **new**, **resolved**, **persistent**
8. Report progress: "3 critical findings resolved, 1 new warning introduced"

---

## Three Passes

### Pass 1 — Deterministic

**Input:** Ontology model + networkx graph built from it.
**Output:** Precise findings with diagnostic IDs.
**Cost:** Cheap. Pure computation, no LLM calls.

Builds a networkx graph once (classes as nodes, subClassOf/domain/range as edges), then runs pattern-matching and graph algorithms.

**Checks covered (~60% of applicable catalog):**

Structural (S-section): connected components, depth analysis, fan-out/fan-in counts, property distribution, axiom-to-class ratio, betweenness centrality, property deserts, linear chains, spectral gap, coupling-cohesion.

Taxonomy (T-section, deterministic subset): flat taxonomy detection, max depth checks, branching factor outliers.

Property (P-section, deterministic subset): multiple domain/range, missing domain/range, domain/range set to owl:Thing, missing inverses, self-inverse, orphan properties, inverse domain/range swap, sub-property domain/range widening.

Naming (N-section): casing convention, plural names, vague/generic names, missing labels, abbreviations, property naming, duplicate labels, hierarchy in labels, redundant namespace, swapped annotations.

Redundancy (D-section): transitive reduction, redundant equivalentClass+subClassOf, duplicate hierarchies.

Metrics (IT-section): information content imbalance, Shannon entropy, relation entropy, relationship richness.

Cross-cutting (CC-section): temporal/spatial/status/measure baking (regex-based).

### Pass 2 — Exploration

**Input:** Ontology + deterministic findings + decision registry.
**Output:** Contextual, holistic findings. Open-ended — not tied to the diagnostic catalog.
**Cost:** Moderate. 1 LLM call per subtree node explored.

A recursive BFS exploration of the class hierarchy with context propagation.

**Mechanics:**

```
explore(node, parent_context, deterministic_findings_for_region)
  → review this node's children as a group
  → informed by: parent_context + deterministic findings in this region
  → produce: findings + summary_context for children
  → for each child subtree worth exploring:
      explore(child, summary_context, ...)
```

**Depth strategy:**
- Default: top 2–3 levels
- Go deeper if findings discovered (drill into problems)
- Go deeper if nothing found (one more level as sanity check, then stop)
- Hard cap: 5–6 levels regardless

**Context propagation:**
Each level passes a concise context summary to its children. Not the full transcript — just the relevant framing:
- Structural observation: "this branch is large/small relative to siblings"
- Quality signal: "parent subtree is well-structured / has issues"
- Scope note: "this region may be out-of-scope per requirements"
- Pattern note: "sibling subtrees use part-whole modeling; check consistency"

**Parallelism:**
Sibling subtrees are independent once they have parent context. All children of a node can be explored in parallel. The only sequential dependency is parent → children.

**What exploration catches that deterministic checks miss:**
- Is-a overloading (T01–T04) — requires semantic judgment
- Surface-name taxonomy (T10) — "GuitarCase subClassOf Guitar"
- Polysemous concepts (T09)
- Umbrella classes (T14)
- Abstraction level mixing (T13)
- Scope creep / domain mismatch (IA01, IA02)
- Compound names without matching structure (M10)
- N-ary relations modeled as binary (M04)
- Missing part-whole patterns (M07)
- Coverage gaps — "the domain needs X but the ontology doesn't have it"
- Holistic assessments — "this subtree is an encyclopedia dump, not a modeled ontology"

**Expansion through exploration:**
The explorer identifies both *problems* and *gaps*. Gaps become findings:
- S05/S08: "these classes are empty shells / this region has no relationships"
- T12: "this branch has 3 classes but the domain warrants 15"
- T06: "this subtree is flat — needs intermediate grouping"
- Coverage: "the requirements mention X but it's absent"

These findings flow through the same resolution pipeline. The fix happens to be additive (expansion) rather than corrective.

### Pass 3 — Resolution

**Input:** All findings (from pass 1 + 2), decision registry.
**Output:** Proposals with 2–3 fix options each, including concrete diffs.
**Cost:** ~1 LLM call per finding, or batched by category.

For each finding, a subagent:
1. Considers the finding in context (affected entities, their neighborhood, registry decisions)
2. Proposes 2–3 fix options with concrete diffs against the ontology model
3. Notes tradeoffs for each option

**Batching strategy** (to reduce LLM calls):
- Batch 1: All taxonomy findings for a subtree → one call
- Batch 2: All property findings → one call
- Batch 3: All naming findings → one call (or auto-fix deterministically)
- Batch 4: All expansion findings for a region → one call

**Force-resolution:** Every finding must be resolved. The main agent:
- Picks an option → decision stored in registry, diff queued for application
- Requests more exploration → subagent explores further
- Explicitly defers → decision stored with reasoning (won't be re-raised unless entities change)

No finding is silently ignored. This ensures the registry fills up, making each subsequent round smarter.

---

## Fix Ordering

Findings are resolved in order of **structural blast radius, top-down.** A fix at the root can cascade across the entire ontology. A naming fix at a leaf affects nothing.

### Tier 1 — Top-level structure (fix first)

Fixes that reshape the class hierarchy. Everything below may need re-evaluation.

- T14: umbrella classes at top levels
- T06: flat taxonomy
- S03: fan-out hotspots at top levels
- S01: disconnected components (do these classes belong?)
- IA01/IA02: domain mismatch, scope creep (remove before fixing)
- Exploration findings about top-level organization

**After tier 1:** Full re-diagnosis. The graph may have changed fundamentally.

### Tier 2 — Taxonomy semantics (fix second)

Fixes that change what classes *are* — reclassification, splitting, merging. These move entities, change edges, alter graph topology.

- T01–T04: is-a overloading (subClassOf → partOf, hasRole, etc.)
- T10: surface-name taxonomy
- T05: instances as classes (move to ABox)
- T09: polysemous concepts (split)
- T13: abstraction level mixing

**After tier 2:** Re-diagnose affected subtrees.

### Tier 3 — Property structure and expansion (fix third)

The class hierarchy is now stable. Fix property modeling and fill gaps.

- P01: multiple domain/range intersection trap
- P03: missing domain/range
- P05: over-specialized domain/range
- P11: redundant per-class properties
- S05/S08: empty shells, property deserts (additive fixes)
- T12: granularity mismatch (additive fixes)
- Coverage gaps from exploration (additive fixes)

**After tier 3:** Re-check properties locally.

### Tier 4 — Naming and cosmetics (fix last)

No structural impact. Safe to batch and auto-fix where possible.

- N01–N11: casing, plurals, labels, annotations
- A01–A07: documentation, provenance
- D01: redundant subClassOf (cleanup)
- CC01–CC04: cross-cutting concern naming patterns

**After tier 4:** No re-diagnosis needed.

### Ordering principle within a tier

**Higher in hierarchy first, then by severity.** A warning at depth 1 before a critical at depth 3. The rationale: a depth-1 fix has larger blast radius and may resolve the depth-3 finding as a side effect.

### Tier assignment heuristic

- Does fixing this change the subClassOf graph topology? → Tier 1–2
- Does it change property structure (domain/range/inverse)? → Tier 3
- Neither? → Tier 4

Some findings span tiers. T08 (missing disjointness) is taxonomy-adjacent but *adds* axioms rather than restructuring — tier 3, not tier 2. S13 (collapsible linear chain) changes structure but is very local — tier 2 but low priority within it. Assign by blast radius of the fix, not by catalog category.

---

## Round Structure

A complete diagnostic round:

```
1. Build/update networkx graph from ontology
2. Run deterministic pass → findings
3. Run exploration pass (receives deterministic findings) → more findings
4. Merge all findings, filter against registry
5. Group by tier, order within tier
6. For current tier:
   a. Run resolution pass → proposals
   b. Main agent reviews proposals → decisions
   c. Store decisions in registry
   d. Apply chosen diffs to ontology
7. Re-diagnose (scope depends on tier)
8. If findings remain in current tier, repeat 6–7
9. Advance to next tier
10. Repeat until all tiers clean or iteration cap reached
```

**Iteration cap:** Per-tier cap (e.g., 3 rounds) + global cap (e.g., 10 rounds total). If a tier isn't converging, surface remaining findings to the user with explanation.

**Convergence check:** If round N has more findings than round N-1 within the same tier, something is wrong — fixes are introducing more problems than they solve. Stop and surface to user.

---

## Progress Reporting

Each round produces a progress report:

- Findings resolved since last round (with what was done)
- New findings introduced (possibly by fixes)
- Persistent findings (still open from previous rounds)
- Metric trends: "modularity: 0.2 → 0.35", "orphan classes: 12 → 3", "naming violations: 28 → 0"
- Current tier and position within it

---

## Applicable Diagnostic Catalog

Checked against current model scope. Reference: DIAGS.md for full descriptions.

### Deterministic checks

**Structural:** S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12, S13, S14, S15
**Taxonomy (structural subset):** T06, T07 (name patterns), T12 (coefficient of variation)
**Property:** P01, P03, P04, P05, P06, P07, P08, P11 (structural similarity), P12, P13, P14, P15, P17 (identical domain+range clusters)
**Naming:** N01, N02, N03, N04, N05, N06, N07, N08, N09, N10, N11
**Redundancy:** D01, D02, D05 (Jaccard over axiom signatures), D06
**Metrics:** IT01, IT02, IT03, IT04
**Cross-cutting:** CC01, CC02, CC03, CC04 (all regex-based)
**Modeling:** M01, M02, M03, M08, M09
**Instance readiness:** IP01

### Exploration pass (LLM judgment)

**Taxonomy:** T01, T02, T03, T04, T05, T09, T10, T11, T13, T14, T15, T16
**Property:** P02, P05, P09, P10, P16, P18
**Modeling:** M04, M05, M07, M10
**Intent alignment:** IA01, IA02, IA03, IA04
**Meta-level:** ML01, ML02
**Coverage gaps** (not in catalog — emergent from exploration)

### Auto-fixable (no LLM needed for the fix)

N01 (re-case), N02 (singularize), R01 (remove minCard 0), P07 (self-inverse → symmetric), P08 (remove redundant inverse on symmetric), D01 (remove redundant subClassOf), D02 (remove redundant subClassOf alongside equivalentClass), N09 (simplify path labels), N11 (swap label/comment), A04 (trim whitespace), M09 (replace "is" property with OWL primitive).

These can be applied directly without going through the resolution pass, reported as "auto-fixed" in progress.

---

## Design Decisions

1. **Auto-fix pass.** Auto-fixable findings are applied silently before the exploration pass. Reported as "auto-fixed" in progress, not routed through the main agent. No reason to ask approval for mechanical corrections like re-casing or whitespace trimming.

2. **Registry persistence.** Per-session only. Each generation is independent. Cross-session persistence may be revisited later if it proves valuable.

3. **User intervention.** Modeling philosophy questions (e.g., "should Student be a role or a subclass of Person?") surface to the user directly. The user is not an ontology engineer, so questions must be framed in plain language with clear options — no OWL jargon. Technical/mechanical decisions are handled by the main agent autonomously. Detailed design of the user interaction model is deferred.

## Open Design Questions

1. **Exploration prompt structure.** Fully open-ended ("review this subtree for quality") vs. checklist-guided ("evaluate: natural partition? similar siblings? appropriate depth? missing groups?") vs. hybrid. Deferred to implementation.

2. **Resolution batching granularity.** One LLM call per finding vs. per category vs. per subtree. Deferred to implementation — will depend on observed cost and quality tradeoffs.
