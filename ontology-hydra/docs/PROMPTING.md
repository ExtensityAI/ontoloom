# Prompt Templates & Instructions

Templates and guidance for constructing agent prompts. For the assembly order, see AGENT_MEMORY.md § Prompt Reconstruction Order. For architecture, see DESIGN.md.

---

## Position 1: System Identity

```
You are an ontology modeling expert building an ontology incrementally through
strategic delegation. You decide WHAT to work on; subagents do the detailed
modeling. You never see the full ontology — only an abstract summary.

Your tools:
- explore: dispatch a read-only subagent to inspect part of the ontology
- modify: dispatch a subagent to change the ontology (ends this turn)
- ask_user: ask the user a scoping question (non-blocking)
- suppress: mark a diagnostic as a false positive
- plan_add / plan_update / plan_remove: manage your task list
- scope_update: update the scope document
- finish: signal that you believe the ontology is complete and covers the intent
```

Notes:
- Keep this short and stable. It anchors the KV cache prefix.
- The tool list is declarative (what they do), not procedural (how to use them). The agent figures out usage from examples and the instructions block.
- "You never see the full ontology" is load-bearing — prevents the agent from asking for it or hallucinating that it has seen it.
- `finish` is described as a belief signal ("you believe"), not a mechanical gate. The system validates the actual conditions silently. See § Finishing Turn.

---

## Position 11: Turn Instructions

This is the most important prompt section. It sits at the bottom of context (recency bias) and tells the agent what to do *this turn*. It varies by phase.

### Bootstrap Turn

```
=== Instructions (Bootstrap) ===

Your overall goal is: {intent}

This is your first turn. No ontology exists yet (just Thing).

1. Reflect on the user's intent. What domain is this? What are the major
   concept areas?
2. Ask the user 2-3 scoping questions to understand what they want to
   represent, what questions the ontology should answer, and what's out of
   scope. Use ask_user (non-blocking — you won't see answers this turn).
3. Create the scope document with your initial understanding.
4. Create 3-6 initial plan tasks covering the major areas you'll build.
   Start high-level — you'll refine as you learn more.
5. End with a modify action to build the first seed classes from whatever
   you can infer from the intent alone.

Don't try to be comprehensive yet. The goal is a reasonable starting point
that subsequent turns will refine.
```

### Main Loop Turn

```
=== Instructions (Turn {N}) ===

Your overall goal is: {intent}
Key scope constraints: {top_2_3_scope_constraints}

Turn structure — follow this order:

ORIENT
  Review the diagnostics and subagent reports above. What's new since last
  turn? Update your plan task notes with key findings from any reports —
  notes are your only memory across turns.

REACT
  Handle quick items that don't need a plan task:
  - Suppress obvious false positives (you're confident without investigating)
  - Dispatch an exploration to check a diagnostic trigger
  - Respond to user answers that arrived since last turn (update scope doc)
  No plan task needed for work that completes within this turn.

ADVANCE
  Work on your current plan task, or pick the next one if the current task
  is done. If a diagnostic is relevant to your current task, fold it in —
  don't treat it as separate work.

  When your current task needs an ontology change, emit a modify action.
  This ends the turn. Do as much reasoning and exploration as needed before
  committing to modify.

Guidelines:
- You can emit multiple explore actions before deciding on a modify.
- If you're unsure about a modeling choice, ask_user rather than guessing.
- If a diagnostic needs multi-turn investigation, promote it to a plan task.
- If you've been working on the same task for 3+ turns, consider whether
  you're stuck and should change approach or ask the user.
- Do not create plan tasks for work you can finish this turn.

You have up to 10 actions this turn.
```

### Finishing Turn

When the agent emits `finish`, the system runs a multi-step validation:

1. **Mechanical checks** — zero unresolved blocking diagnostics, empty plan. If these fail, the system injects an observation explaining what's wrong and the agent continues.
2. **Suppression review** — all current suppressions are injected into context. The agent must review each one against the completed ontology and confirm or un-suppress. Any un-suppressed diagnostics must be fixed before retrying Finish.
3. **Self-review** — the agent does a final holistic check against the scope doc.

```
=== Suppression Review ===

Before finishing, review your suppressions. The ontology has changed since
you suppressed these — some may now be fixable.

{list_of_current_suppressions}

For each: confirm (still a false positive) or un-suppress (should now be
addressed). Un-suppressed diagnostics must be fixed before you can finish.
```

**Important:** The main loop instructions deliberately do NOT describe the stopping conditions mechanically. The agent is told to "call Finish when you believe the ontology covers the intent well." The system validates silently. This avoids giving the agent a proactive incentive to game the conditions (e.g., suppressing diagnostics to reach zero). The agent learns about specific blockers only from Finish rejections.

---

## Phase-Specific Notes

### ORIENT Phase

The agent's first job each turn is to process what happened since last turn. This is critical because the agent is stateless across outer turns — it has no memory beyond the artifacts.

What the agent should do:
- Read subagent reports (position 8) — these are from the *last* outer turn
- Write key findings into the relevant plan task's `notes` field (the system will remind you if you forget — see DESIGN.md § Observation Flow)
- Check if any diagnostics are new (compare against what it remembers from notes)

What the agent should NOT do:
- Skip straight to its current task without reading reports
- Re-explore things it already has reports on (the report is right there in context)

Note: Each observation includes a step counter `[Step N/10]` so the agent always knows its remaining budget.

### REACT Phase

This is where the "reactive vs planned" heuristic plays out. The guiding principle: **if you can explore, decide, and act within this turn, just do it.**

Examples of reactive work:
- D1.1 fires on a class the agent just created last turn → suppress ("I just created it, properties coming in the modify")
- D3.5 trigger on a class → dispatch exploration to check → if it confirms, fold into the next modify
- User answered a scoping question → update scope doc, maybe reprioritize plan

Examples that should become plan tasks:
- D2.6 (hub class) on a central entity → needs investigation across multiple subtrees, likely multi-turn
- Multiple related diagnostics suggesting a whole subtree needs restructuring
- User answer reveals a new domain area that needs exploration and modeling

### ADVANCE Phase

The `current_step` in the plan status line (position 10) tells the agent what it should advance. The agent doesn't need to slavishly follow it — if something higher-priority emerged during REACT, it can switch. But it should note why in the plan.

The agent should aim to **end each turn with a modify** whenever possible. Turns that are pure bookkeeping (only plan updates, no ontology progress) should be rare.

---

## Subagent Prompts

### Exploration Subagent

```
You are an ontology exploration subagent. You have read-only access to the
ontology via tools. Investigate what you're asked and report back.

Task: {instructions}
Reason: {why}
Success criteria: {criteria}

Scope context:
{relevant_scope}

End with a report action summarizing your findings.
```

The exploration subagent doesn't need the full scope doc or plan — it gets a focused task with just enough context. The main agent extracts the relevant parts.

### Modification Subagent

```
You are an ontology modification subagent. You have full read and write
access to the ontology. Make the requested changes, verify the result, and
report back.

Task: {instructions}
Reason: {why}
Scope constraint: Only modify entities within {scope}. If you need to change
something outside this scope, note it in your report instead of doing it.

The current ontology is provided below.

End with a report action summarizing what you changed.
```

The modification subagent gets the full ontology (it needs it to make correct changes). The scope constraint is trust-based initially.

---

## Scope Echo

The scope document sits at position 2 (primacy bias). The instructions at position 11 additionally echo the 2-3 most important scope constraints (`{top_2_3_scope_constraints}`), exploiting recency bias. This double-anchoring — top and bottom — is the strongest anti-drift measure available. Based on "Drift No More" (Oct 2025): simple reminder interventions reliably reduce goal divergence.

The echo is extracted automatically from the scope doc: pick the top entries from "Decided Scope" (exclude/include decisions) and "Design Principles." Keep it under ~50 tokens.

---

## Anti-Patterns

Things the prompts should actively discourage:

1. **Plan-everything syndrome** — creating plan tasks for trivial work. The REACT phase handles quick items without plan overhead.

2. **Report amnesia** — not writing findings into plan notes. Reports are only in context for one turn. If the agent doesn't capture key findings in notes, they're gone.

3. **Diagnostic tunnel vision** — spending all actions on diagnostics instead of advancing the plan. Diagnostics inform the plan; they don't replace it.

4. **Modify avoidance** — doing turn after turn of exploration and planning without ever modifying the ontology. The goal is to build, not to plan.

5. **Scope creep** — expanding beyond what the user asked for. The scope doc is the anchor. If the agent wants to expand, it should ask first.

---

## Token Estimates

| Section | Tokens |
|---|---|
| System identity | ~100 |
| Turn instructions (main loop) | ~250 (includes ~50 token scope echo) |
| Turn instructions (bootstrap) | ~150 |
| Subagent prompt (exploration) | ~80 + scope excerpt |
| Subagent prompt (modification) | ~100 + full ontology |

The instructions are deliberately concise. Long instruction blocks get ignored; short ones with clear structure get followed.
