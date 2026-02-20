# Artifact Schemas & Prompt Assembly

Reference for artifact formats and prompt reconstruction. For architecture, decisions, and invariants, see DESIGN.md. For prompt templates and turn instructions, see PROMPTING.md.

## Prompt Reconstruction Order

At the start of each **outer turn**, the agent's prompt is assembled from artifacts in this order:

```
1. System identity + role description
2. Scope document (FULL — drift anchor, always near top)
3. Suppression list (FULL)
4. Ontology summary (abstract, current state)
5. Plan (FULL — active tasks with statuses, provenance, and notes)
6. Compressed action log (one line per past outer turn)
7. Current diagnostics (unsuppressed only)
8. Most recent subagent reports (FULL — all reports from the last outer turn)
9. Pending user responses from prior AskUser (if any)
10. Plan status line (compact: progress, current step, churn rate)
11. Instructions for this turn
```

**Why this order:**
- Scope doc near the top because it's the drift anchor — the thing the agent should always be aware of.
- Plan before diagnostics so the agent sees its roadmap before new issues. Diagnostics feed into the plan, not the other way around.
- Full subagent reports at position 8 — the agent needs these to make decisions. Reports from older turns are not included; the agent's `notes` field is the durable memory across turns.
- Plan status line near the bottom for recency bias — gives the agent immediate orientation ("where am I, what's next") without scanning the full plan.

---

## Artifact Formats

### Scope Document — Semi-Structured Markdown

```markdown
## User Goals
- [Original user request — never modified]

## Decided Scope
### [Domain Area]
- Include: ...
- Exclude: ... (user decision, turn N)
- Granularity: ...

### [Domain Area]
- [pending user decision on ...]

## Design Principles
- [Principle] (source: user/agent, turn N)
```

**Rules:**
- The scope doc is the drift anchor. It is NEVER summarized or compacted.
- Always included in full in the prompt.
- The agent writes it; the user can correct it.
- Each entry records provenance (which turn, user or agent decision).
- Soft guidance, not hard boundaries.

### Plan — Structured JSON

```json
{
  "revision": 5,
  "current_step": "t7",
  "tasks": [
    {
      "id": "t7",
      "task": "Expand Vehicle subclass hierarchy",
      "status": "pending | in_progress | blocked",
      "priority": "high | medium | low",
      "notes": "Exploration found: 3 subclasses (Car, Truck, RedVehicle). RedVehicle has no unique properties — candidate for D3.5/D3.8.",
      "added_turn": 4,
      "added_reason": "User requested detailed vehicle taxonomy",
      "depends_on": null,
      "attempted": null,
      "blocked_reason": null
    }
  ]
}
```

**Top-level fields:**
- `revision` — increments on structural changes (add/remove/reorder tasks), not on status or notes updates. Tracks plan churn. If `revision / turn` is high, the agent is thrashing.
- `current_step` — the `id` of the task the agent is currently working on. Updated automatically by the system when a task moves to `in_progress`.

**Task fields:**
- `notes` — the agent's working memory and synthesis. Updated within the inner loop (as observations come back) and across outer turns (notes persist). The agent should write key findings from subagent reports into `notes` during the turn they're received — this is the durable memory across turns. **Hard limit: ~500 characters per task.** The system warns the agent when a notes update approaches the limit. This prevents notes bloat from crowding out other context. If the limit is consistently insufficient, revisit with workspace file persistence (see IDEAS.md § Workspace Files).

**Rules:**
- Every item has `added_reason` (provenance). This prevents the agent from treating items as arbitrary.
- **Done tasks are removed from the plan** by the system after the outer turn where they complete. The action log captures the outcome (see below). The plan only contains active work.
- Blocked items include `blocked_reason` (e.g., "needs user decision").
- The agent can add, complete, split, remove, and re-prioritize freely — the plan is a scratchpad, not a contract.
- Task IDs use the `t` prefix (`t1`, `t2`, ...). Sequential, never reused.

### Compressed Action Log — One Line Per Outer Turn

```
Turn 1: [BOOTSTRAP] Scope document created. 4 initial plan tasks.
Turn 2: [EXPLORE] Vehicle domain. Report: 12 classes proposed.
Turn 3: [ASK_USER] Excluded watercraft. Scope updated.
Turn 4: [MODIFY] Added 8 vehicle subclasses. 7 succeeded, 1 conflict.
Turn 5: [EXPLORE] Diagnostic D2.6 on Vehicle. Suppressed (intentional hub).
Turn 6: [DONE t5] Expanded Vehicle subtree → 8 subclasses, excluded watercraft per user.
Turn 7: [MODIFY] Fixed property domains for Sensor hierarchy.
```

**Rules:**
- One line per outer turn, ~20-30 tokens each.
- Format: `Turn N: [ACTION_TYPE] Brief description. Key outcome.`
- When a plan task completes, the system writes a `[DONE tN]` entry that captures the task name and a summary from the task's `notes` field. This is the **outcome record** — prevents the agent from re-proposing completed work.
- Append-only. Never edited or compacted.
- Gives the agent trajectory awareness ("am I going in circles?") at minimal token cost.

### Suppression List — Structured

```json
[
  {
    "diagnostic_id": "D2.6",
    "entity": "Vehicle",
    "reason": "Intentional hub class per user's domain structure",
    "suppressed_turn": 5,
    "entity_hash": "abc123"
  }
]
```

The `entity_hash` is a fingerprint of the entity's structural properties at suppression time. If the hash changes (entity modified), the suppression resurfaces.

---

## Plan Status Line

A compact summary injected near the end of context (position 10). Generated automatically by the system:

```
=== Plan Status (rev 5, turn 14) ===
Progress: 7 done, 1 in progress, 4 pending
Current: [t8] Add object properties for Sensor subtree
Next: [t9] Investigate D2.6 on Vehicle
Churn: 0.36 (5 revisions / 14 turns)
```

~40 tokens. Gives the agent immediate orientation without scanning the full plan or action log.

---

## Token Budget

| Artifact | Include | Size |
|---|---|---|
| Scope doc | Always, FULL | Grows slowly, ~500-2000 tokens |
| Plan (active tasks only) | Always, FULL | ~50-100 tokens per item |
| Suppression list | Always, FULL | ~30 tokens per entry |
| Action log | Always, FULL | ~20-30 tokens per outer turn |
| Latest subagent reports | Always, FULL | ~200-500 tokens per report |
| Plan status line | Always, compact | ~40 tokens (fixed) |
| Older subagent reports | Never | Agent's `notes` field is the durable memory |
| Full ontology | Never | Agent sees abstract summary only |

**Budget estimate at turn 50:** ~3,000-5,000 tokens for artifacts listed above (excluding system prompt, tool definitions, ontology summary, and last-turn subagent reports). With those included, realistic total is **~5,000-12,000 tokens** depending on ontology size and domain complexity. The ontology summary alone can reach ~2,000-4,000 tokens for 200+ classes. Done tasks are removed from the plan, keeping it lean. Monitor actual token usage during testing — if budget pressure emerges, see IDEAS.md § Workspace Files.

---

## Sources

- [ReAct: Reasoning and Acting (Yao et al., ICLR 2023)](https://arxiv.org/abs/2210.03629)
- [Let Me Speak Freely? Format restrictions degrade reasoning (Tam et al., EMNLP 2024)](https://arxiv.org/abs/2408.02442)
- Natural Language Tools (Johnson et al., 2025) — 18.4pp accuracy gain over JSON tool calling [URL placeholder — verify]
- [IterResearch: Markovian State Reconstruction (2025)](https://arxiv.org/abs/2511.07327)
- [Anthropic: Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Letta/MemGPT: Memory Concepts](https://docs.letta.com/concepts/memgpt/)
- [Cognition AI: Don't Build Multi-Agents](https://cognition.ai/blog/dont-build-multi-agents)
- [Agentic Memory (2025)](https://arxiv.org/html/2601.01885v1)
- [Cognitive Design Patterns for LLM Agents](https://arxiv.org/html/2505.07087v2)
- [How Agents Plan Tasks with To-Do Lists](https://towardsdatascience.com/how-agents-plan-tasks-with-to-do-lists/)
- [Single vs Multi-Agent Systems](https://www.philschmid.de/single-vs-multi-agents)
- [Google ADK: Multi-Agent Systems](https://google.github.io/adk-docs/agents/multi-agents/)
- [ACE: Agentic Context Engineering](https://arxiv.org/abs/2510.04618)
