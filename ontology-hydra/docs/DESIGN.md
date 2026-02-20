# Agent Design — Invariants & Decisions

## Role

The agent is the **strategic driver** of ontology construction. It replaces the current hard-coded outer loop (`generate_ontology`'s 50-iteration cycle).

The agent never does detailed ontology modeling itself. It delegates all exploration and modification to subagents.

## Core Principles

- The agent operates at a **strategic level** — it decides *what* to work on, not *how* to model it.
- The agent has an **abstract view** of the ontology (hierarchy tree with names, counts, diagnostics). It never sees raw property definitions, descriptions, or full JSON.
- All detailed work (exploration, modification) is **delegated to subagents**.
- The agent builds domain understanding **incrementally** through user interaction and its own judgment.

## Key Artifacts

### Scope Document

A living document the agent maintains, capturing accumulated decisions about what's in/out of scope and general domain guidance. Written by the agent, correctable by the user. Soft guidance, not hard boundaries. Always included in full in the prompt — it's the **drift anchor**. See AGENT_MEMORY.md for the template.

### Plan

The agent's primary working document for deciding what to do next.

- Items range from **vague/strategic** ("flesh out the Sensor hierarchy") to **concrete** ("investigate diagnostic #12").
- The agent can add, complete, split, and remove items freely — it's a scratchpad, not a contract.
- Items originate from: bootstrap phase, diagnostics, user requests, or the agent's own analysis.
- The agent works *from* the plan: checks `current_step`, works on it, moves to the next item. Diagnostics, user input, and the agent's own judgment feed *into* the plan by creating, reprioritizing, or removing items.
- **Plan items are for work that spans outer turns.** Not every action needs a plan item. The agent can freely investigate a diagnostic, suppress it, or do quick reactive work within the inner loop without plan overhead. Plan items track substantial goals that need multiple steps or will span multiple turns.
- The heuristic: if the agent can explore → decide → act within one inner loop, no plan item. If the work will carry over to the next outer turn (needs a modify, needs user input, needs further investigation), create a plan item so the context survives the turn boundary.
- Each item has a **notes** field — the agent writes findings from exploration here. This is the working memory for multi-turn tasks. The agent updates notes within the inner loop (as observations come back) and across outer turns (notes persist in the plan).
- **Done tasks are removed from the plan** by the system after the outer turn where they complete. The system writes a `[DONE tN]` entry in the action log capturing the outcome. The plan only contains active work (pending, in_progress, blocked).
- The plan has a `revision` counter that tracks structural churn (add/remove/reorder). High `revision / turn` ratio signals the agent is thrashing.
- See AGENT_MEMORY.md for the full JSON schema.

### Action Log

One-line-per-outer-turn compressed history. Append-only, never edited. Gives the agent trajectory awareness ("am I going in circles?"). When a plan task completes, the system writes a `[DONE tN]` entry that captures the outcome — this is the **re-work prevention** mechanism (replaces the "done list" in the plan). See AGENT_MEMORY.md for format details.

### Diagnostics

Three tiers:

1. **Deterministic** — structural issues (e.g., class with no properties or parent).
2. **Semantic** — potential modeling issues detected by analysis (e.g., two properties that seem duplicated).
3. **Heuristic** — patterns that *might* indicate problems but could be intentional.

**Execution model:**
- **Always run (included in agent's prompt every outer turn):** All Tier 1 checks + deterministic *triggers* from Tier 2/3. A trigger is a cheap heuristic that flags a candidate — e.g., "subclass has no unique properties" (D3.5 trigger), "two class names are WordNet synonyms" (D3.3 trigger). The trigger surfaces the candidate; the agent decides whether to investigate.
- **On-demand (agent dispatches exploration):** Full Tier 2/3 analysis. The exploration subagent reads the diagnostic hint and follows it using its tools. This costs an action but produces a definitive judgment.
- Diagnostics are **recomputed after every ontology change** (summary and triggers refresh automatically).

**Suppressions (severity-gated):**
- **Critical diagnostics: never suppressible.** Must be fixed.
- **Important diagnostics: suppressible only after investigation.** The agent must dispatch an exploration subagent that confirms the diagnostic is a false positive. Drive-by suppression without investigation is rejected by the system.
- **Minor diagnostics: freely suppressible** with a reason.
- Tied to a specific entity (class or property).
- Automatically **resurface** if the associated entity changes (domain/range modification, rename, etc.).
- Automatically **deleted** if the entity is deleted.

See DIAGNOSTICS.md § Suppression Model for full details.

## Agent's View

See AGENT_MEMORY.md § Prompt Reconstruction Order for the full assembly sequence (11 items).

The agent does NOT see:
- Property definitions, descriptions, domain/range details
- Full ontology JSON
- Raw metric distributions

## Actions

All agents (main agent and subagents) use the same unified format: natural language reasoning interleaved with `<action>` blocks containing type-discriminated JSON.

### Action Types

| Type | Category | What it does |
|---|---|---|
| `explore` | Read-only | Delegate exploration subagent to examine a subtree, property, area, or diagnostic. Multiple explores can be dispatched in parallel within a single inner loop step — they are read-only, so no consistency risk. |
| `ask_user` | Read-only | Ask the user a scoping question. Non-blocking: agent continues; answer arrives on a future turn |
| `modify` | Write | Delegate modification subagent. Ends the outer turn (ontology changes → recompute diagnostics/summary) |
| `finish` | Terminal | Signal that the ontology is complete. System validates silently; rejected with explanation if conditions not met |
| `suppress` | Bookkeeping | Mark a diagnostic as false positive. Severity-gated: Critical never, Important requires prior investigation, Minor free. See DIAGNOSTICS.md § Suppression Model |
| `plan_add` | Bookkeeping | Add a plan task (increments plan revision) |
| `plan_update` | Bookkeeping | Update a plan task (status, notes, priority). Status/notes changes don't increment revision; priority changes do. |
| `plan_remove` | Bookkeeping | Remove a plan task (increments plan revision) |
| `scope_update` | Bookkeeping | Update the scope document |

### Inner Loop (ReAct)

The main agent runs in a **ReAct loop** within each outer turn:

1. Agent reasons in natural language, emits `<action>` blocks
2. System executes actions (runs subagents for explore, delivers ask_user, processes bookkeeping)
3. Observations injected back into context
4. Agent sees results, reasons more, emits more actions
5. Loop continues until agent emits `modify` (ends outer turn), `finish` (terminal), or no more actions

**Sequencing rule:** Read-only + bookkeeping actions freely within the loop. Once the agent emits `modify`, the system executes it and the outer turn ends. `finish` is always exclusive.

**Inner loop cap:** 10 steps per outer turn (safety net — should never be reached in practice).

**Step countdown:** Each observation injected into context includes a step counter: `[Step 4/10]`. Gives the agent budget awareness without requiring it to track steps internally. Prevents the agent from running out of steps without realizing it.

Subagents also run in ReAct loops with their own tools (exploration tools, mutation tools).

## Exploration Subagent

A general-purpose read-only agent with tools to inspect the ontology. The main agent tells it what to look at and why. It returns a structured report.

**Tools:**

| Tool | What it does |
|---|---|
| `get_class(name)` | Class with description, parents, all data/object properties where it appears in domain or range |
| `get_subtree(root)` | All descendants of a class with their properties |
| `get_property(name)` | Full property details (description, domain, range) |
| `search(query)` | Fuzzy name/description search across classes and properties |
| `get_neighbors(class_name)` | Classes connected via object properties |
| `get_diagnostics(scope?)` | Run full diagnostics (including LLM-assisted), optionally scoped to a class/subtree |
| `get_summary()` | The ontology summary |
| `get_full_ontology()` | The complete ontology (gated — only available for small ontologies) |

## Modification Subagent

Receives the **full ontology** + instructions describing what to change + a scope constraint. Has access to **all exploration tools** (same as the exploration subagent) **plus the mutation API**. This lets it: investigate the current state, plan changes, make changes, and verify the result — all autonomously.

Each mutation operation returns a **diff view** showing exactly what changed (entities added/removed/modified, references updated). This gives the subagent immediate feedback.

Scope enforcement is trust-based initially (instructions only), enforced later as a post-condition.

### Mutation API

Fine-grained atomic operations. Each does one thing. Each returns success/failure + what changed. Validation is **eager** — invalid operations are rejected with an error explaining why.

**Class operations:**

| Operation | Parameters | Notes |
|---|---|---|
| `add_class` | name, description, parents | Fails if name already exists |
| `delete_class` | name | Cascades: removes from all property domains/ranges, other classes' sub_class_of. Diff shows all cascaded changes. |
| `rename_class` | name, new_name | Atomic: cascades to all references (properties, sub_class_of) |
| `update_class_description` | name, description | |
| `move_class` | name, new_parents | Replaces sub_class_of list |

**Data property operations:**

| Operation | Parameters | Notes |
|---|---|---|
| `add_data_property` | name, description, domain, range | |
| `delete_data_property` | name | Diff shows what was removed |
| `rename_data_property` | name, new_name | Atomic cascade |
| `update_data_property_description` | name, description | |
| `set_data_property_domain` | name, domain | Replaces domain list |
| `set_data_property_range` | name, range | Changes the DataType |

**Object property operations:**

| Operation | Parameters | Notes |
|---|---|---|
| `add_object_property` | name, description, domain, range | |
| `delete_object_property` | name | Diff shows what was removed |
| `rename_object_property` | name, new_name | Atomic cascade |
| `update_object_property_description` | name, description | |
| `set_object_property_domain` | name, domain | Replaces domain list |
| `set_object_property_range` | name, range | Replaces range list |

**Composite operations:**

| Operation | Parameters | Notes |
|---|---|---|
| `merge_classes` | source_classes, target_name, description | Unions properties, updates all references, removes sources |

More composites can be added later if the LLM consistently fumbles specific multi-step sequences (e.g., `convert_class_to_data_property`, `split_class`).

## Delegation Patterns

Subagents never modify the scope doc, plan, or suppression list directly. The main agent makes all strategic decisions.

### Dispatch Context

When delegating, the main agent provides:

1. **Task description** — what to do
2. **Why** — the reason this task is being performed
3. **Success criteria** — what a good result looks like
4. **Relevant scope** — initially the full scope doc; later, extracted relevant parts
5. **Relevant ontology context** — the subtree or area being worked on

### Subagent Report Format

Subagents emit a `report` action as their final output:

```
<action>
{"type": "report", "report": {
  "task_echo": "What I was asked to do and why",
  "status": "completed | partial | failed",
  "result_summary": "One paragraph of what happened",
  "changes_made": [],
  "ambiguities_found": [],
  "conflicts_detected": [],
  "recommendations": []
}}
</action>
```

The system extracts this report and delivers it to the main agent as an `<observation>` block.

**The `task_echo` field is critical.** It re-establishes context in two places: (1) within the inner loop, when the main agent reads the report; (2) at the start of the next outer turn, when last-turn reports are included in the prompt.

### Handling Failures

- Failed subagents still return a report with `status: "failed"` and explanation.
- Main agent decides: retry with different instructions, narrow the scope, or escalate to user.
- Failed plan tasks get `attempted: { turn: N, result: "failed", reason: "..." }` — prevents infinite retry loops.
- Max 1-2 retries before changing approach.

## Bootstrap Phase

A structured first phase before the main loop:

1. Agent presents its understanding of the intent back to the user.
2. Asks the user to describe what they want in richer terms: what data to represent, what questions to answer, what to store. (Competency-style questions as soft guidance, not a hard spec.)
3. Optionally asks follow-up scoping questions.
4. Seeds the scope document with what it learned.
5. Uses its own ontology modeling expertise to generate an initial plan (major concept areas to model).

The ontology starts as a **minimal seed** (just `Thing` with a label). The first Modify action builds from there.

The user is NOT expected to know everything upfront. The bootstrap captures initial direction; the scope doc grows organically as the agent encounters ambiguity.

## Stopping Conditions

All must be true:
- **Zero unresolved blocking diagnostics** — all Critical diagnostics fixed; all Important diagnostics either fixed or investigated-and-suppressed (see Suppression Model below). Unconfirmed triggers alone do NOT block Finish — they are candidates, not confirmed problems.
- **Empty plan** (all tasks completed or removed).
- **Suppression review** — before Finish succeeds, the system injects all current suppressions into context and asks the agent to review them: "In the context of the completed ontology, are these suppressions still valid? Un-suppress any that should now be fixable." This catches diagnostics the agent suppressed early (when the ontology was small) that are now addressable.
- **Agent self-review** — a final holistic check: "does this ontology coherently cover the stated intent?" This is the agent's judgment call, informed by the scope doc.

**Important:** The agent's prompt does NOT describe these conditions mechanically. Instead, it frames finishing in terms of quality: "call Finish when you believe the ontology covers the intent well." The system validates the conditions silently. If Finish is rejected, the rejection explains what's wrong. This avoids giving the agent a perverse incentive to game the conditions.

## Agent Output Format

All agents produce natural language reasoning interleaved with `<action>` blocks. This is the ReAct pattern — think out loud, then emit structured calls. Unified format for main agent and subagents.

**Main agent example:**
```
D3.5 triggered on RedVehicle — no unique properties, single parent. I need
to investigate the Vehicle subtree before deciding whether to restructure.

<action>
{"type": "explore", "target": "Vehicle subtree", "instructions": "Check subclasses of Vehicle. For each, list unique properties (not inherited). Report which have zero unique properties."}
</action>

<action>
{"type": "plan_update", "id": "t3", "status": "in_progress", "notes": "D3.5 triggered. Exploring Vehicle subtree."}
</action>
```

**After observation, in the same outer turn:**
```
Exploration shows RedVehicle has zero properties while Car has 2 and Truck has 3.
This confirms D3.5 — RedVehicle should be a property, not a class. I can also
suppress D3.8 since the real issue is D3.5.

<action>
{"type": "suppress", "diagnostic_id": "D3.8", "entity": "RedVehicle", "reason": "Subsumed by D3.5 — class will be converted to property"}
</action>

<action>
{"type": "modify", "scope": "Vehicle subtree", "instructions": "Convert RedVehicle from a subclass of Vehicle into a data property 'vehicleColor' on Vehicle. Remove the RedVehicle class. Keep Car and Truck unchanged."}
</action>
```

**Subagent example (exploration):**
```
Let me check what properties RedVehicle has.

<action>
{"type": "get_class", "args": {"name": "RedVehicle"}}
</action>
```

**Subagent example (modification):**
```
I'll rename the class first, then update its description.

<action>
{"type": "rename_class", "args": {"name": "RedVehicle", "new_name": "ColoredVehicle"}}
</action>
```

**Implementation:**
- System parses `<action>` blocks via regex: `r'<action>(.*?)</action>'`
- JSON inside each block validated against Pydantic schemas (discriminated union on `type`)
- Stop sequence at `<observation>` prevents hallucinated results
- On parse failure: inject error message, retry (max 2 retries)
- Natural language between actions serves as chain-of-thought reasoning + human-readable trace
- Research basis: ReAct (Yao et al., 2022), "Let Me Speak Freely" (Tam et al., 2024) — free-form reasoning + structured calls outperforms fully structured output by 10-27%

## State Management

### Markovian State Reconstruction

The agent's long-term "memory" is its artifacts. If it's not in an artifact, it doesn't exist. This scales to 1000+ turns where continuous context accumulation fails due to "context suffocation."

Two levels:

**Across outer turns: stateless.** The main agent does not maintain a continuous conversation. Each outer turn, the agent's prompt is reconstructed from persisted artifacts (see AGENT_MEMORY.md § Prompt Reconstruction Order for the full assembly sequence).

The agent has no memory of prior outer turns beyond what's captured in these artifacts. To preserve context, the agent **provides context when dispatching subagents** (why, what it expects) and **subagents echo that context in their reports** (via `task_echo`). This makes the agent inherently **resumable** — if the process crashes, it can reconstruct state from artifacts.

**Within an outer turn: conversational.** The main agent runs a ReAct loop — it accumulates context from its own reasoning and observations within the turn. This lets it explore → see results → reason → explore more → suppress → modify, all in one outer turn.

### Preventing Drift

Three mechanisms, layered:

1. **Drift anchor (scope doc)** — always in full at the top of the prompt. Contains the user's goals and all accumulated decisions. Never summarized.
2. **Provenance tracking** — every plan task records why it was added (`added_reason`). Every scope doc entry records which turn and whether it was a user or agent decision. The agent can always trace back "why am I doing this?"
3. **Action log** — completed work is recorded as `[DONE tN]` entries. The agent checks "have I already done X?" before proposing it.

**Additional measure: scope echo.** The prompt instructions (item 11) begin with the goal and the 2-3 most important scope constraints, exploiting both primacy (scope doc at position 2) and recency (echo at position 11) bias. See PROMPTING.md § Scope Echo.

## Error Handling

### Error Taxonomy

Errors are classified by who can fix them:

| Type | Who fixes | Action |
|---|---|---|
| **Transient** (API timeout, rate limit) | System | Automatic retry with backoff. Handled transparently within subagents — never surfaces to main agent. |
| **LLM-recoverable** (malformed output, wrong approach) | Agent/Subagent | Feed error into context, retry with adjusted approach. Max 2 retries before changing strategy. |
| **User-fixable** (ambiguous scope, domain question) | Human | Pause via `ask_user`. Agent continues other work if possible. |
| **Structural** (ontology inconsistency, unresolvable conflict) | Agent | Try different approach. If stuck, escalate to user or abandon task with explanation. |

### Subagent Failures

Subagents **always return a report**, whether they succeed or fail. On failure, the report explains what went wrong and why. The main agent then decides how to proceed — retry with different instructions, try a different approach, ask the user, or abandon and remove the plan item.

Transient errors (API timeouts, rate limits) are handled transparently within subagents via automatic retry with backoff. The main agent never sees these.

No automatic retries at the main agent loop level beyond the transient tier. The agent has full discretion.

## Persistence

All agent state is persisted to the cache:

- Scope document
- Plan (with task statuses and notes)
- Suppression list (with entity links and reasons)
- Action log (append-only, one line per outer turn)
- Subagent reports (from last outer turn only — older reports are not persisted; the agent's plan `notes` field is the durable memory)
- Ontology snapshots (after each modification)

**Deterministic serialization:** All persisted artifacts that appear in the prompt must serialize deterministically across turns. Use `sort_keys=True` for JSON (plan, suppression list). Use a fixed traversal order for the ontology summary (e.g., alphabetical within each hierarchy level). Non-deterministic serialization silently breaks KV-cache prefix matching — a single reordered key invalidates the cache from that point forward.

Resumability is a future engineering concern — the persistence model supports it, but the resume logic itself is deferred.

## Observation Flow

**Within the inner loop (read-only actions):**
- Subagent reports injected as `<observation>` blocks into the agent's context, with step counter: `[Step N/10]`
- Agent sees results immediately and can reason about them
- Agent should update relevant plan task `notes` with key findings from reports during this turn — notes are the only thing that persists across outer turns

**After a modify action (ends outer turn):**
1. Updated ontology is persisted
2. Ontology summary is recomputed
3. Diagnostics are recomputed (suppressions checked for resurfacing)
4. **Extraction confirmation** — the system checks whether the agent updated plan task notes during this turn. If subagent reports were received but no `plan_update` with notes changes was emitted, the system injects a reminder: "You received subagent reports this turn but didn't capture findings in your plan notes. Notes are your only memory across turns — update them now before the turn ends." The agent gets one additional step to update notes before the turn boundary.
5. All artifacts persisted
6. Next outer turn starts with fresh prompt reconstruction

## Constraints

- **Modify ends the outer turn** — within the ReAct loop, read-only + bookkeeping freely. Once modify emits, it executes and the outer turn ends.
- **Inner loop cap: 10 steps** per outer turn (safety net — should never be reached). If hit in >20% of turns during testing, raise to 15. Research suggests 15-25 is typical for production agent frameworks.
- **`max_steps`** caps total outer turns (cost/runaway guardrail).
- **No user-initiated interruption** during the agent loop (user only responds to AskUser).

## What's Deferred

- Subtree extraction for modification subagent (start with full ontology + focus instructions).
- Intelligent scope doc extraction for subagent prompts (start with full copy).
- Scope enforcement for modification subagent (start trust-based via instructions, enforce as post-condition later).
- Competency question verification as a formal step (rely on agent judgment for now).
- Resume logic (persistence model supports it, implementation later).
- Additional composite operations (`split_class`, `convert_class_to_data_property`, etc.) — add if LLM fumbles specific sequences.
- Exact JSON schema for each `<action>` type (finalize during implementation).
- Plan notes staleness detection (observe if the agent handles it naturally first; add entity tracking if needed).
- Workspace file persistence and reversible compaction — if the `notes` field becomes a bottleneck (see IDEAS.md § Workspace Files).
- OWL reasoner integration (HermiT/ELK) — not applicable with the current simplified model (no axioms, no restrictions), but becomes critical if the model gains OWL expressivity. Every peer system (NeOn-GPT, LLMs4Life, Ontogenia) includes reasoner validation.
- Ontology checkpointing and rollback — snapshots are already persisted after each Modify, but automated rollback on diagnostic degradation is not implemented. Consider: "if critical diagnostic count increased, offer the agent a rollback option."
