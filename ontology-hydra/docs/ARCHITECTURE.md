# System Architecture

> Core architecture for the diagnostics-driven ontology generation system.

---

## Overview

The system builds ontologies through an iterative diagnose/resolve loop:

```
bootstrap → initial draft → [diagnose → resolve] → ... → clean
```

There is no separate "expansion" phase. Expansion is an emergent property of fixing incompleteness diagnostics — when a finding says "this branch is under-modeled," the fix adds content. Correction and expansion flow through the same pipeline. Every addition is justified by a diagnostic finding, preventing scope creep by design.

The system has three roles:
- **Main agent** — strategic driver. Decides *what* to work on, delegates all detailed work. Sees an abstract summary of the ontology, never the full model (see [SUMMARIZATION.md](SUMMARIZATION.md)).
- **Exploration subagent** — read-only inspector. Examines subtrees, properties, and diagnostics. Returns structured reports (see [EXPLORATION.md](EXPLORATION.md)).
- **Resolution subagent** — produces fix proposals with concrete diffs. Receives findings and generates 2–3 options per finding (see [RESOLUTION.md](RESOLUTION.md)).

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
- IntersectionOf / UnionOf (beyond what the model uses for domain/range)
- Property characteristics (functional, symmetric, transitive)
- Disjointness axioms
- Embedding-based checks (deferred — see [FUTURE.md](FUTURE.md))
- Reasoner-based checks (deferred — see [FUTURE.md](FUTURE.md))

A single meta-diagnostic reports: "this ontology is purely taxonomic — no restrictions, no defined classes, no disjointness." This captures the absence of axioms as one info-level finding.

This scope covers ~55–60% of the full diagnostic catalog ([CATALOG.md](CATALOG.md)), targeting the highest-value checks for LLM-generated ontologies. The checker interface is designed to be axiom-agnostic so checkers can be added as the model gains expressivity.

---

## Core Data Model

### Finding

What's wrong (or missing). Produced by deterministic checks or the exploration pass.

- **diagnostic_id** — catalog reference (e.g., "S03", "T01") or "EXP" for exploration findings
- **severity** — critical / warning / info
- **affected_entities** — list of class/property names involved
- **description** — human-readable explanation of the problem
- **tier** — fix ordering tier (1–4, see [RESOLUTION.md](RESOLUTION.md) § Fix Ordering)
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

**Metrics history** — per-round snapshots of graph metrics (depth, fan-out distribution, modularity, etc.). Enables progress reporting: "modularity improved from 0.2 to 0.4."

**Decision registry** — see above.

**Previous ontology snapshot** — the full ontology from the prior round. Used with entity hashes to compute the change set.

### Incremental Re-Diagnosis

On rounds after the first:

1. Diff current ontology against previous snapshot → `ChangedEntities`
2. Compute dirty set: changed entities + their 1-hop graph neighbors
3. Re-check by scope tier:
   - **Entity-local checks** (N01, P03, etc.): re-check only dirty set
   - **Neighborhood checks** (T08, S03, T01–T04): re-check only dirty set
   - **Global checks** (S01, S07, S14, IT metrics): always re-run (cheap — networkx on <500 nodes)
4. **Exploration pass**: only re-explore subtrees containing modified entities
5. Diff findings against previous round → **new**, **resolved**, **persistent**
6. Report progress: "3 critical findings resolved, 1 new warning introduced"

---

## Round Structure

A complete diagnostic round:

```
1. Build/update networkx graph from ontology
2. Run auto-fix pass (mechanical corrections — recasing, whitespace, etc.)
3. Run deterministic pass → confirmed findings + candidate findings
4. Run exploration pass (receives candidates + deterministic context) → more findings
5. Merge all findings, filter against decision registry
6. Group by tier, order within tier (see RESOLUTION.md § Fix Ordering)
7. For current tier:
   a. Run resolution pass → proposals
   b. Main agent reviews proposals → decisions
   c. Store decisions in registry
   d. Apply chosen diffs to ontology
8. Re-diagnose (scope depends on tier — see RESOLUTION.md § Re-Diagnosis Scope)
9. If findings remain in current tier, repeat 7–8
10. Advance to next tier
11. Repeat until all tiers clean or iteration cap reached
```

**Auto-fix pass (step 2):** Auto-fixable findings are applied silently before exploration. Reported as "auto-fixed" in progress, not routed through the main agent. No reason to ask approval for mechanical corrections like re-casing or whitespace trimming. See [CATALOG.md](CATALOG.md) § Auto-Fixable Diagnostics for the full list.

**Iteration cap:** Per-tier cap (e.g., 3 rounds) + global cap (e.g., 10 rounds total). If a tier isn't converging, surface remaining findings to the user with explanation.

**Convergence check:** If round N has more findings than round N-1 within the same tier, something is wrong — fixes are introducing more problems than they solve. Stop and surface to user.

---

## Lifecycle

### Phase 1: Bootstrap

A structured first phase before the main loop. The agent understands the domain, asks scoping questions, creates the scope document, and generates an initial ontology seed. See [BOOTSTRAP.md](BOOTSTRAP.md) for full details.

### Phase 2: Main Loop

Iterative diagnose/resolve cycles. Each round processes one tier of findings (top-level structure → taxonomy → properties → naming). The agent reviews proposals and makes decisions, which accumulate in the registry.

### Phase 3: Stopping

All must be true:
- **All tiers clean or explicitly deferred** — every finding either fixed or deferred with reasoning in the decision registry.
- **Decision review** — before declaring done, the system surfaces all deferred decisions for reconsideration against the completed ontology. Decisions made early (when the ontology was small) may now be addressable.
- **Self-review** — a final holistic check: "does this ontology coherently cover the stated intent?" Informed by the scope document.

---

## Interaction Model

Two modes:

- **Interactive** — the system surfaces modeling philosophy questions to the user. The user is not an ontology engineer, so questions are framed in plain language with clear options — no OWL jargon. Technical/mechanical decisions are handled autonomously. See [BOOTSTRAP.md](BOOTSTRAP.md) § User Interaction.
- **Fully automatic** — no user interaction. The agent makes all scoping decisions using its modeling expertise.

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
- Metric trends: "modularity: 0.2 → 0.35", "orphan classes: 12 → 3", "naming violations: 28 → 0"
- Current tier and position within it

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

## Token Budget

| Component | Tokens (est.) |
|---|---|
| System identity | ~100 |
| Ontology summary (50 classes) | ~800–1000 |
| Ontology summary (200 classes) | ~1500–2000 |
| Diagnostics (per round) | ~200–500 |
| Decision registry (50 decisions) | ~1000–1500 |
| Progress report | ~100–200 |
| Prompt instructions | ~250 |

The ontology summary is the dominant variable cost. Compression strategies keep it under ~2000 tokens even for 200+ class ontologies (see [SUMMARIZATION.md](SUMMARIZATION.md)).

---

## Design Decisions (Resolved)

1. **No separate expansion phase.** Expansion emerges from fixing incompleteness diagnostics. One system: diagnose → resolve.

2. **Structured Pydantic model, not raw OWL.** LLMs produce syntactically invalid Turtle regularly. Update/delete is nearly impossible with raw strings. Diffs are painful with unstructured output. The diagnostics architecture assumes programmatic access. Use Turtle as a display format in prompts where it helps the LLM reason, not as the data model.

3. **Auto-fix pass before exploration.** Mechanical corrections (re-casing, whitespace, redundant edges) are applied silently. Reported but not routed through the main agent.

4. **Per-session registry only.** Each generation is independent. Cross-session persistence may be revisited if it proves valuable.

5. **User questions in plain language.** Modeling philosophy questions (e.g., "should Student be a role or a subclass of Person?") surface with clear options, no OWL jargon.
