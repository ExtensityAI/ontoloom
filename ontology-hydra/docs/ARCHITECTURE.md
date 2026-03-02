# System Architecture

> Core architecture for the diagnostics-driven ontology generation system.

---

## Overview

The system builds ontologies through an iterative diagnose/resolve loop:

```
bootstrap → initial draft → [diagnose → resolve] → ... → clean
```

There is no separate "expansion" phase. Expansion is an emergent property of fixing incompleteness diagnostics — when a finding says "this branch is under-modeled," the fix adds content. Correction and expansion flow through the same pipeline. Every addition is justified by a diagnostic finding, preventing scope creep by design.

The system has four roles:
- **Orchestrator** — deterministic Python code. Runs the diagnostic loop: executes passes, dispatches subagents, enforces phase gates and iteration caps, applies diffs, manages session state. All control flow lives here — predictable, debuggable, testable.
- **Main agent** — LLM decision reviewer. Reviews proposals and picks options (or defers). Sees an abstract summary of the ontology, never the full model (see [SUMMARIZATION.md](SUMMARIZATION.md)). Also chooses which subtree to work on next (see § Round Structure, step 7). Its reasoning is stored in the decision registry and propagates to future rounds.
- **Exploration subagent** — LLM read-only inspector. Examines subtrees, properties, and diagnostics. Has autonomy in *how* it explores (which tools to call, how deep to go) but not *what* to explore (dispatched by the orchestrator). Returns structured reports (see [EXPLORATION.md](EXPLORATION.md)).
- **Resolution subagent** — LLM fix proposer. Receives findings and generates 2–3 fix options with concrete diffs. Has autonomy in *how* it designs fixes but not *what* to fix (dispatched by the orchestrator). See [RESOLUTION.md](RESOLUTION.md)).

---

## Scope

The system operates on the current `Ontology` model:

- `owl:Class` + `rdfs:subClassOf`
- `owl:ObjectProperty` + `owl:DatatypeProperty`
- `rdfs:domain` + `rdfs:range`
- `rdfs:subPropertyOf`
- `owl:inverseOf`

**Explicitly out of scope (for now):**
- Multiple inheritance — `sub_class_of` restricted to a single parent. Cross-cutting classification axes are modeled via object properties (see [PATTERNS.md](PATTERNS.md) § P.08). The main OWL argument for multiple inheritance (Rector Normalization) requires defined classes + equivalence axioms, which are not in the current model. Re-enable when the model gains those features.
- Restrictions (someValuesFrom, allValuesFrom, cardinality)
- Equivalence class definitions
- IntersectionOf / UnionOf (beyond what the model uses for domain/range)
- Property characteristics (functional, symmetric, transitive)
- Disjointness axioms
- Embedding-based checks (deferred — see [FUTURE.md](FUTURE.md))
- Reasoner-based checks (deferred — see [FUTURE.md](FUTURE.md))

A single meta-diagnostic reports: "this ontology is purely taxonomic — no restrictions, no defined classes, no disjointness." This captures the absence of axioms as one info-level finding.

This scope covers ~55–60% of the full diagnostic catalog ([CATALOG.md](CATALOG.md)), targeting the highest-value checks for LLM-generated ontologies. The checker interface is designed to be axiom-agnostic so checkers can be added as the model gains expressivity.

**Note on graph metrics:** Earlier versions included several network-science metrics (betweenness centrality, Newman modularity, small-world property, spectral gap). These were removed after literature review showed they are uninformative for ontology class hierarchies — betweenness is redundant for trees, modularity is meaningless on sparse DAGs, and no reference ontology has published baseline values for small-world σ. The system retains simpler, validated metrics: depth, fan-out, leaf count, property counts per class, and Relationship Richness (IT04). See [CATALOG.md](CATALOG.md) § Removed Diagnostics for details.

---

## Core Data Model

### Finding

What's wrong (or missing). Produced by deterministic checks or the exploration pass.

- **diagnostic_id** — catalog reference (e.g., "S03", "T01") or "EXP" for exploration findings
- **severity** — critical / warning / info
- **affected_entities** — list of class/property names involved
- **description** — human-readable explanation of the problem
- **phase** — fix ordering phase (1–3, see [RESOLUTION.md](RESOLUTION.md) § Fix Ordering)
- **kind** — `confirmed` or `candidate`

**Confirmed findings** are definitively wrong (deterministic checks with zero ambiguity). **Candidate findings** are flagged by cheap heuristic triggers — the exploration pass investigates and either confirms or dismisses them (see [EXPLORATION.md](EXPLORATION.md) § Candidate Findings).

### Proposal

A finding with concrete fix options. Produced by the resolution pass.

- **finding** — the underlying finding
- **options** — 2–3 fix alternatives, each with:
  - **description** — what this option does
  - **diff** — concrete modification to the ontology model
  - **tradeoffs** — what you gain/lose

### Decision

The main agent's response to a proposal. Stored in the decision registry.

- **proposal** — what was proposed
- **chosen_option** — which fix was selected (or "defer")
- **reasoning** — why this choice was made
- **scope** — global (applies everywhere) or local (applies to specific entities)

---

## Decision Registry

The registry accumulates decisions across rounds, making each subsequent round smarter. Consulted before raising findings — if a finding was already resolved (fixed or explicitly deferred with reasoning), it is not re-raised unless the relevant entities changed.

**Note:** No existing ontology engineering methodology (NeOn, DILIGENT, METHONTOLOGY) formalizes accumulated design decisions that suppress re-raising of resolved issues. DILIGENT's argumentation framework is the closest analog but serves distributed team coordination, not agent self-management. The decision registry is a novel mechanism for this system.

### Global Decisions

Pattern-level choices that apply everywhere:

- "We model roles as separate classes with hasRole properties."
- "We use singular UpperCamelCase for all class names."
- "Part-whole relationships use hasPart/isPartOf, not subClassOf."

### Per-Entity Decisions

Entity-specific rulings:

- "Vehicle: 15 direct subclasses is intentional — they have distinct property signatures."
- "Student: modeled as role, not subclass of Person."
- "MeetingRoom3B: kept as class, not instance — serves as template."

### Properties

Each decision carries:
- **chosen_option** — what was decided
- **reasoning** — why (prevents oscillation across rounds)
- **alternatives_considered** — what was rejected
- **scope** — global vs. local

### Force-Resolution

Every finding must be resolved. The main agent:
- Picks an option → decision stored, diff queued for application
- Requests more exploration → subagent investigates further
- Explicitly defers → decision stored with reasoning (won't be re-raised unless entities change)

No finding is silently ignored. This ensures the registry fills up, enabling incremental re-diagnosis.

---

## Session State

A `DiagnosticSession` is created per generation run and holds all mutable state. Not persisted across sessions.

### State Components

**Entity content hashes** — hash of each entity's semantically relevant fields (name, subClassOf, domain, range, description, etc.). Used to compute diffs between rounds. Field-level granularity — any field change marks the entity as dirty.

**LLM judgment cache** — `(diagnostic_id, entity_content_hash)` → judgment result. If the entity hasn't changed, reuse the cached judgment. Invalidated when the entity or any 1-hop neighbor changes.

**Embedding cache** — `(entity_name, entity_definition_hash)` → vector. Only embed new/changed entities. Deferred but the slot exists in the design.

**Metrics history** — per-round snapshots of simple graph metrics (depth, fan-out distribution, property counts, relationship richness). Enables progress reporting: "orphan classes: 12 → 3", "relationship richness: 0.15 → 0.35."

**Decision registry** — see above.

**Exploration journal** — persistent cross-round observations from the explorer. Qualitative signal about recurring problem areas, cross-subtree patterns, and coverage notes. See [EXPLORATION.md](EXPLORATION.md) § Exploration Journal.

**Previous ontology snapshot** — the full ontology from the prior round. Used with entity hashes to compute the change set.

### Incremental Re-Diagnosis

On rounds after the first:

1. Diff current ontology against previous snapshot → `ChangedEntities`
2. Compute dirty set: changed entities + their 1-hop graph neighbors
3. Re-check by scope:
   - **Entity-local checks** (N01, P03, etc.): re-check only dirty set
   - **Neighborhood checks** (T08, S03, T01–T04): re-check only dirty set
   - **Global checks** (S01, IT04, simple graph metrics): always re-run (cheap — networkx on <500 nodes)
4. **Exploration pass**: only re-explore subtrees containing modified entities
5. Diff findings against previous round → **new**, **resolved**, **persistent**
6. Report progress: "3 critical findings resolved, 1 new warning introduced"

---

## Round Structure

A complete diagnostic round. Steps marked `[orchestrator]` are deterministic code; steps marked `[LLM]` involve an LLM call.

```
1.  [orchestrator] Build/update networkx graph from ontology
2.  [orchestrator] Run auto-fix pass (mechanical corrections — recasing, whitespace, etc.)
3.  [orchestrator] Run deterministic pass → confirmed findings + candidate findings
4.  [LLM]          Run exploration pass (dispatch explorer subagents per subtree) → more findings
5.  [orchestrator] Merge all findings, filter against decision registry
6.  [orchestrator] Group by phase, order within phase (see RESOLUTION.md § Fix Ordering)
7.  [LLM]          Main agent chooses which subtree to work on next (from available options)
8.  [orchestrator] Build batch from chosen subtree (3–8 related findings)
9.  [LLM]          Run resolution pass → proposals for the batch
10. [LLM]          Main agent reviews proposals → decisions (pick option, defer, or request different exploration)
11. [orchestrator] Store decisions in registry, apply chosen diffs to ontology
12. [orchestrator] Re-diagnose (scope depends on phase — see RESOLUTION.md § Re-Diagnosis Scope)
13. If findings remain in current subtree, repeat 8–12
14. If subtree is clean, return to step 7 for next subtree
15. If all subtrees in current phase are clean, advance to next phase
16. Repeat until all phases clean or iteration cap reached
```

**Auto-fix pass (step 2):** Auto-fixable findings are applied silently before exploration. Reported as "auto-fixed" in progress, not routed through the main agent. See [CATALOG.md](CATALOG.md) § Auto-Fixable Diagnostics for the full list.

**Subtree selection (step 7):** The orchestrator presents the main agent with available subtrees and their finding summaries. The main agent chooses which to work on next — this is a strategic decision point. For v1, a pure heuristic (highest-priority subtree) is acceptable if adding the LLM call proves unnecessary.

**Batch building (step 8):** Each batch targets a coherent group of related findings within the chosen subtree. Batch size: 3–8 findings. See [RESOLUTION.md](RESOLUTION.md) § Batching Strategy for details.

**Iteration caps:** Per-batch cap (3 rounds without finding count decreasing → surface to user), per-phase cap (Phase 2: 15 rounds; Phases 1 and 3: 3 rounds each), global cap (20 rounds total). If a cap is hit, surface remaining findings to the user with explanation.

**Convergence:** A batch converges when its finding count is monotonically non-increasing across rounds. If a fix introduces new findings (common in Phase 2 expansion), this is expected — the cap prevents runaway loops.

---

## Lifecycle

### Phase 1: Bootstrap

A structured first phase before the main loop. The agent understands the domain, asks scoping questions, creates the scope document, and generates an initial ontology seed. See [BOOTSTRAP.md](BOOTSTRAP.md) for full details.

### Diagnostic Loop

Iterative diagnose/resolve cycles in three phases. Each round processes a batch of findings within a subtree of the current phase. The agent reviews proposals and makes decisions, which accumulate in the registry.

**Phase 1 — Foundation:** Top-level structural integrity and scope alignment. Full re-diagnosis after each round. Phase 1 → 2 is a hard gate (all subtrees must pass).

**Phase 2 — Modeling:** Taxonomy semantics, property structure, and expansion. Per-subtree advancement — clean subtrees proceed independently. Findings ordered by blast radius within each subtree (reclassification → structural additions → property adjustments), but this is a heuristic default, not a hard gate. Coherent proposals that span taxonomy and properties are encouraged.

**Phase 3 — Polish:** Naming, annotations, documentation, cosmetic cleanup. No re-diagnosis needed.

See [RESOLUTION.md](RESOLUTION.md) § Fix Ordering for detailed phase contents and ordering rules.

### Stopping

All must be true:
- **All phases clean or explicitly deferred** — every finding either fixed or deferred with reasoning in the decision registry.
- **Coverage satisfied** — all active coverage assertions derived from user documents are satisfied or explicitly deferred (see [BOOTSTRAP.md](BOOTSTRAP.md) § Document Index).
- **Decision review** — before declaring done, the system surfaces all deferred decisions for reconsideration against the completed ontology. Decisions made early (when the ontology was small) may now be addressable.
- **Self-review** — a final holistic check: "does this ontology coherently cover the stated intent?" Informed by the scope document and user documents. Includes a full-depth exploration pass (not limited by the usual depth strategy).

These conditions are checked by the system, not described to the agent mechanically. The agent is told to finish "when you believe the ontology covers the intent well." The system validates silently. If conditions aren't met, the rejection explains what's wrong. This avoids giving the agent a perverse incentive to game the conditions (e.g., deferring everything to reach "all clean").

---

## Interaction Model

Two modes:

- **Interactive** — the system surfaces modeling philosophy questions to the user. The user is not an ontology engineer, so questions are framed in plain language with clear options — no OWL jargon. Technical/mechanical decisions are handled autonomously. See [BOOTSTRAP.md](BOOTSTRAP.md) § User Interaction.
- **Fully automatic** — no user interaction. The agent makes all scoping decisions using its modeling expertise.

### Input

The user provides:
- **Intent** — what the ontology is for, what domain, what purpose. Informs the abstraction level (what belongs in the ontology vs. in a knowledge graph).
- **Domain documents** (required) — source material about the domain. Database schemas, requirements docs, sample records, API specs, textbook chapters, etc. These ground the system in real domain content.

### Output

The user receives:
- The ontology (JSON model)
- A summary report: scope document, diagnostic history, decision log, what was built and why

---

## Progress Reporting

Each round produces a progress report:

- Findings resolved since last round (with what was done)
- New findings introduced (possibly by fixes)
- Persistent findings (still open from previous rounds)
- Auto-fixes applied (with counts)
- Metric trends: "orphan classes: 12 → 3", "relationship richness: 0.15 → 0.35", "naming violations: 28 → 0"
- Current phase, subtree, and position within it
- Coverage assertion status (N satisfied / M active)

---

## Error Handling

### Error Taxonomy

| Type | Who fixes | Action |
|---|---|---|
| **Transient** (API timeout, rate limit) | System | Automatic retry with backoff. Handled transparently — never surfaces to main agent. |
| **LLM-recoverable** (malformed output, wrong approach) | Subagent | Feed error into context, retry. Max 2 retries before changing strategy. |
| **User-fixable** (ambiguous scope, domain question) | Human | Surface to user in interactive mode. In automatic mode, agent uses best judgment. |
| **Structural** (unresolvable conflict, regression) | Agent | Try different approach. If stuck, escalate to user or defer with explanation. |

### Regression Detection

If applying a fix causes the critical finding count to increase, the system flags this as a regression. The main agent can choose to roll back (previous snapshot is always available) or investigate why the fix introduced new problems.

---

## Persistence & Serialization

All session state is persisted after each round:
- Ontology snapshots (after each modification)
- Decision registry
- Metrics history
- Finding history (for progress reporting)

**Deterministic serialization:** All artifacts that feed into prompts must serialize deterministically across rounds. Use `sort_keys=True` for JSON, fixed traversal order for the ontology summary (alphabetical within each hierarchy level). Non-deterministic serialization silently breaks KV-cache prefix matching — a single reordered key invalidates the cache from that point forward.

**Ontology checkpointing:** Snapshots are persisted after each round. Automated rollback on diagnostic regression is not yet implemented but the persistence model supports it. See [FUTURE.md](FUTURE.md) for details.

---

## Context Hygiene

### Tool Result Compaction

After the main agent processes a subagent report (exploration or resolution), the full report is replaced in conversation history with a compact summary (~50–100 tokens). The full report persists in session state if needed for reference, but does not occupy context in subsequent turns.

This prevents old tool results from accumulating and eating context. An exploration report for a large subtree can be 500+ tokens; after the main agent has made decisions based on it, only the summary matters: "Explored Vehicle subtree: 3 findings (T01 on Car, T13 on RedVehicle, S05 on GroundVehicle), 2 candidates dismissed."

### Subagent Context Assembly Logging

During development, log the exact context each subagent receives — the assembled prompt with all interpolated values. This makes it possible to diagnose "why did the explorer miss this obvious problem?" by inspecting what information the explorer actually had access to.

Not a runtime feature — a development/debugging aid. Should be toggleable via a session-level debug flag.

---

## Token Budget

| Component | Tokens (est.) |
|---|---|
| System identity | ~100 |
| Ontology summary (50 classes) | ~3000 |
| Ontology summary (200 classes) | ~4000–5000 |
| Diagnostics (per round) | ~200–500 |
| Decision registry (50 decisions) | ~1000–1500 |
| Progress report | ~100–200 |
| Prompt instructions | ~250 |

The ontology summary is the dominant variable cost. It uses Turtle format — full detail for small ontologies, progressively compressed for larger ones. No fixed token budget; compression is driven by context pressure at runtime. See [SUMMARIZATION.md](SUMMARIZATION.md).

---

## Implementation Scope

The docs describe the full system design. Not everything is needed for v1. The distinction: v1 validates the core thesis (iterative diagnose/resolve produces better ontologies than single-shot generation). Incremental additions improve quality and efficiency after the core is proven.

### v1 (Core)

- **Bootstrap:** intent + documents → document index → scope document → seed ontology
- **Deterministic pass:** confirmed findings only (no trigger/candidate system)
- **Exploration pass:** review subtrees with tools and document research, but fixed depth (no confidence gating, no random probes). Property-driven cross-cuts included.
- **Resolution pass:** generate proposals with hints, main agent picks options
- **Decision registry:** simple list of decisions with reasoning. No global/local distinction needed yet.
- **Three-phase system:** Phase 1 gate before Phase 2. Per-subtree advancement in Phase 2.
- **Incremental re-diagnosis:** hash-based dirty sets for deterministic checks. Only re-explore subtrees with changes.
- **Scope document + scope echo**
- **Auto-fix pass**
- **Document research subagent** with exact-match caching

### Incremental (after core validated)

- **Candidate findings / trigger system** — deterministic triggers that produce candidates for exploration to confirm/dismiss. Adds nuance but the exploration pass already catches these issues independently.
- **Confidence-gated stopping** — explorer reports confidence, low confidence triggers deeper exploration. Optimization for exploration efficiency.
- **Random deep probes** — ~20% of clean subtrees get full-depth probes. Catches false negatives from shallow review.
- **Exploration journal** — persistent cross-round observations. Valuable after many rounds; in early rounds there's little to accumulate.
- **Semantic cache matching** — reuse document research answers for semantically similar questions. Exact-match caching is sufficient for v1.
- **Tool result compaction** — compress old subagent reports in conversation history. Defer until context pressure is actually observed.
- **Post-generation iteration** — resume with user feedback after completion. See [FUTURE.md](FUTURE.md) § Post-Generation Iteration.

---

## Design Decisions (Resolved)

1. **No separate expansion phase.** Expansion emerges from fixing incompleteness diagnostics. One system: diagnose → resolve.

2. **Structured Pydantic model, not raw OWL.** LLMs produce syntactically invalid Turtle regularly. Update/delete is nearly impossible with raw strings. Diffs are painful with unstructured output. The diagnostics architecture assumes programmatic access. Use Turtle as a display format in prompts where it helps the LLM reason, not as the data model.

3. **Auto-fix pass before exploration.** Mechanical corrections (re-casing, whitespace, redundant edges) are applied silently. Reported but not routed through the main agent. See [RESOLUTION.md](RESOLUTION.md) § Auto-Fix for the full list and exclusions.

4. **Per-session registry only.** Each generation is independent. Cross-session persistence may be revisited if it proves valuable.

5. **User questions in plain language.** Modeling philosophy questions (e.g., "should Student be a role or a subclass of Person?") surface with clear options, no OWL jargon.

6. **Three phases, not four tiers.** Taxonomy and property work merged into a single Modeling phase (bidirectional dependency). See [RESOLUTION.md](RESOLUTION.md) § Fix Ordering for the full rationale.

7. **Documents required.** User-provided domain documents ground the system in real content instead of LLM training data. Documents serve as reference during bootstrap (informing scoping decisions) and during exploration (grounding coverage gap detection). See [BOOTSTRAP.md](BOOTSTRAP.md) § Document-Grounded Bootstrap.

8. **Simple graph metrics only.** Network-science metrics (betweenness centrality, Newman modularity, small-world property, spectral gap) were removed after literature review showed they are uninformative for ontology class hierarchies. The system uses simpler validated metrics: depth, fan-out, property counts, and Relationship Richness (IT04).

9. **Deterministic orchestrator, not LLM orchestrator.** The diagnostic loop is a Python state machine, not an LLM agent with tools. All control flow (phase gates, iteration caps, dirty-set computation, diff application) is deterministic code. LLMs are invoked at specific decision points: exploration, resolution, and proposal review. This is predictable, debuggable, and testable. The main agent has strategic input at two points — subtree selection and proposal review — but does not control the loop. Designed for progressive agency expansion: if the main agent's strategic input proves valuable, its decision points can be expanded toward a full LLM-orchestrated loop without changing the subagent architecture.
