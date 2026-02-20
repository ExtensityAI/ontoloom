# Agent System — High-Level Plan

## What We're Building

An agent that constructs ontologies through strategic delegation. It understands the user's domain, decides what to work on, delegates detailed work to subagents, and interacts with the user when decisions are ambiguous. It replaces the current blind 50-iteration loop with an intelligent, goal-directed process.

## The Flow

### 1. User starts a run

The user provides an intent (e.g., "an ontology for IoT sensor networks") and a config. The system creates a run directory and cache, then enters the bootstrap phase.

### 2. Bootstrap phase

Structured first turn: agent understands the domain, asks scoping questions, creates the scope document and initial plan. Ontology starts as a minimal seed (`Thing`). See DESIGN.md § Bootstrap Phase, PROMPTING.md § Bootstrap Turn.

### 3. Main loop

Each outer turn: reconstruct prompt from artifacts → agent runs ReAct inner loop (ORIENT → REACT → ADVANCE) → system persists changes → next turn. The agent is stateless across outer turns. See DESIGN.md § Inner Loop (ReAct), PROMPTING.md § Main Loop Turn.

### 4. Stopping

The agent calls Finish when it believes the ontology is complete. The system validates: zero unresolved blocking diagnostics, empty plan, suppression review, and agent self-review. `max_steps` exists as a safety net. See DESIGN.md § Stopping Conditions.

### 5. Output

The user gets:
- The ontology JSON
- Optionally a summary report (scope doc, diagnostic history, what was built and why)

## Interaction Model

Two modes:
- **Interactive** — the agent asks the user questions via AskUser; progress is visible via a TUI (similar to Claude Code). The user sees what the agent is doing and responds to questions.
- **Fully automatic** — no user interaction. The agent makes all scoping decisions on its own using its modeling expertise. AskUser is disabled or self-answered.

hydra-viz serves as a debugging/inspection tool for watching the ontology evolve during or after a run.

## The Artifacts

Six persisted artifacts that constitute the agent's entire state:

| Artifact | What it is | Who writes it |
|---|---|---|
| **Scope document** | Accumulated decisions about what's in/out of scope, user goals, design principles | Agent |
| **Plan** | Structured task list with statuses, provenance, and notes. Primary working document. | Agent (tasks), System (revision, current_step) |
| **Suppression list** | Diagnostics marked as false positives, tied to specific entities | Agent |
| **Action log** | One-line-per-outer-turn compressed history | System (automatic) |
| **Ontology** | The actual ontology being constructed | Modification subagents |
| **Subagent reports** | Results of the most recent delegated actions (last outer turn only) | Subagents |

See AGENT_MEMORY.md § Artifact Formats for detailed schemas and rules.

## What Changes in the Existing Code

| Current | New |
|---|---|
| `generate_ontology` command with 50-iteration loop | Agent loop with bootstrap + main loop |
| `generate_plan` → `implement_plan` per iteration | Modification subagent uses mutation API (atomic operations + composites) |
| Full ontology JSON in planning prompts | Ontology summary for main agent; full ontology for subagents |
| Metrics computed per iteration | Diagnostics computed after each modification |
| No user interaction during generation | AskUser for scoping decisions |
| Fixed iteration count | Agent-driven stopping with `max_steps` safety net |
| No persistent working state | Plan with structured notes as durable memory across turns |

## Implementation Order

1. **Ontology summarization** — the agent's view of the ontology
2. **Deterministic diagnostics** — structural checks the agent reacts to
3. **Agent loop skeleton** — stateless-per-outer-turn loop with artifact persistence and prompt reconstruction
4. **Bootstrap phase** — first-turn prompt and initial artifact creation
5. **AskUser + scope doc** — user interaction and scope document mechanics
6. **Explore action** — exploration subagent with ontology query tools
7. **Modify action** — modification subagent with mutation API
8. **Suppress** — diagnostic suppression flow
9. **Semantic diagnostics** — computational checks (Phase 2)
10. **Heuristic/LLM diagnostics** — LLM-assisted checks (Phase 3)

Steps 1-5 give a working agent that can bootstrap, plan, ask the user questions, and manage a plan — but can't yet modify the ontology. Steps 6-7 add the core capability. Steps 8-10 add polish.

## Reference Documents

- **DESIGN.md** — invariants, architectural decisions, constraints, action types, mutation API, subagent tools
- **DIAGNOSTICS.md** — full catalog of 30 diagnostic checks across 3 tiers, execution model, suppression model
- **AGENT_MEMORY.md** — state management patterns, prompt reconstruction order, artifact formats, delegation patterns
- **PROMPTING.md** — prompt templates, turn structure (ORIENT/REACT/ADVANCE), subagent prompts, anti-patterns
- **SUMMARIZATION.md** — ontology summary format, compression strategies, examples
- **IDEAS.md** — future ideas not part of initial implementation
