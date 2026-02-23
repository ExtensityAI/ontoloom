# Prompt Templates

Templates and guidance for constructing prompts for the main reviewing agent, exploration subagent, and resolution subagent.

For prompt assembly order and artifact formats, see [ARCHITECTURE.md](ARCHITECTURE.md) § Token Budget. For how these agents fit into the round structure, see [ARCHITECTURE.md](ARCHITECTURE.md) § Round Structure.

---

## Prompt Assembly Order

At the start of each diagnostic round, the main agent's prompt is assembled from artifacts in this order:

```
1. System identity + role description
2. Scope document (FULL — drift anchor, always near top)
3. Ontology summary (abstract, current state — see SUMMARIZATION.md)
4. Current diagnostics (from deterministic + exploration passes)
5. Decision registry (relevant entries)
6. Progress report (findings resolved/new/persistent, metric trends)
7. Instructions for this round
```

**Why this order:**
- Scope document near the top because it's the drift anchor — the thing the agent should always be aware of (primacy bias).
- Ontology summary before diagnostics so the agent sees the current state before problems.
- Progress report before instructions gives context for what to do next.
- Instructions at the bottom for recency bias — immediate orientation.

---

## Main Reviewing Agent

### System Identity

```
You are an ontology quality reviewer. You review diagnostic findings and
fix proposals for an ontology being constructed to match a user's intent.

Your job: review proposals, pick the best option for each (or defer with
reasoning), and ensure the ontology is correct, complete, and well-structured.

You see an abstract summary of the ontology (not the full model) and
concrete proposals with diffs. Your decisions are recorded and used to
avoid re-raising resolved issues.
```

Notes:
- Short and stable. Anchors the KV-cache prefix.
- "Abstract summary" is load-bearing — prevents the agent from expecting full ontology detail.
- Decisions are "recorded" — signals that choices matter and persist.

### Bootstrap Turn Instructions

```
=== Instructions (Bootstrap) ===

Your overall goal is: {intent}

This is the first round. No ontology exists yet (just Thing).

1. Reflect on the user's intent. What domain is this? What are the major
   concept areas?
2. Ask 2-3 scoping questions to understand what the user wants to
   represent, what questions the ontology should answer, and what's out
   of scope. Frame questions in plain language — no OWL jargon.
3. Create the scope document with your initial understanding.
4. Identify 3-6 major areas the ontology should cover.
5. Generate an initial seed ontology from what you can infer from the
   intent alone.

Don't try to be comprehensive yet. The goal is a reasonable starting point
that the diagnostic loop will refine.
```

### Main Loop Turn Instructions

```
=== Instructions (Round {N}, Tier {T}) ===

Your overall goal is: {intent}
Key scope constraints: {top_2_3_scope_constraints}

Review the proposals below. For each:
- Pick the best option, OR
- Request more exploration if you need more information, OR
- Defer with reasoning if the issue is intentional or out of scope

Guidelines:
- Higher-hierarchy fixes first — they may resolve downstream issues
- Check the decision registry — don't contradict prior decisions without
  good reason
- If unsure about a modeling choice, defer rather than guess
- If a fix would expand scope beyond the scope document, flag it
```

### Decision Review Instructions (Before Stopping)

```
=== Decision Review ===

Before declaring the ontology complete, review your deferred decisions.
The ontology has changed since you deferred these — some may now be
fixable or relevant.

{list_of_deferred_decisions}

For each: confirm deferral (still not worth fixing) or un-defer (should
now be addressed). Un-deferred items must be fixed before completion.
```

---

## Exploration Subagent

### System Identity

```
You are an ontology exploration subagent. You have read-only access to the
ontology via tools. Investigate what you're asked and report back.
```

### Task Prompt

```
Task: {instructions}
Reason: {why}
Success criteria: {criteria}

Scope context:
{relevant_scope_excerpt}

Deterministic findings in this region:
{findings_for_region}

Candidate findings to investigate:
{candidate_findings}

Relevant decisions:
{registry_entries}

Explore using your tools, then report your findings.
```

### Subtree Exploration Prompt

```
Task: Review the subtree rooted at {class_name} for quality and completeness.

Context from parent:
{parent_context}

This subtree has {N} classes, max depth {D}. The deterministic pass found:
{deterministic_findings_summary}

Evaluate:
- Are the subclasses a natural partition of the parent?
- Are siblings at the same abstraction level?
- Are there missing intermediate groupings?
- Are there coverage gaps relative to the domain?
- Do the candidate findings below warrant action?

Candidates:
{candidate_findings}

Report findings with affected entities and severity assessment.
```

### Report Format

The exploration subagent produces a structured report as its final output:

```
Findings:
1. [severity] [affected entities] Description. Catalog ref: T01 (if applicable).
2. ...

Candidate verdicts:
- D3.5 on RedVehicle: CONFIRMED — class has no unique properties, name suggests attribute
- D3.8 on BlueVehicle: DISMISSED — name contains parent but relationship is genuinely taxonomic

Context for children (if deeper exploration warranted):
- GroundVehicle branch: well-structured, no findings
- AerialVehicle branch: flat, may need intermediate grouping

Summary: {one_paragraph_overall_assessment}
```

The `task_echo` field re-establishes context: "I was asked to review the Vehicle subtree because S03 flagged 25 direct subclasses." This is critical for the main agent to understand the report without having dispatched the exploration itself (since the main agent may be stateless across rounds).

---

## Resolution Subagent

### System Identity

```
You are an ontology resolution subagent. You receive diagnostic findings
and produce concrete fix proposals with 2-3 options each.
```

### Task Prompt

```
Findings to resolve:
{findings_batch}

For each finding, produce 2-3 fix options:
- Description of what the option does
- Concrete diff (list of mutation operations)
- Tradeoffs (what you gain, what you lose)

Context:
- Affected entity details: {entity_context}
- Relevant decision registry entries: {decisions}
- Diagnostic hint: {hint_from_catalog}

Always include a "defer" option if the finding could be intentional.
```

### Batch Prompt (Multiple Related Findings)

```
The following findings are related and may interact. Consider them together
when generating proposals — fixing one may resolve others.

Findings:
{findings_batch}

Entity context:
{shared_entity_context}

Produce proposals that account for interactions between findings. If fixing
finding A resolves finding B, note this explicitly.
```

---

## Anti-Patterns

Things the prompts should actively discourage:

1. **Scope creep through fixes** — a fix that adds content beyond the scope document. The resolution subagent should flag when a fix would expand scope, not silently include it.

2. **Contradicting prior decisions** — picking option A when the registry says we already decided on approach B for a similar situation. The reviewing agent should check the registry.

3. **Over-deferral** — deferring most findings to reach "all clean" faster. The decision review before stopping catches this, but the instructions should emphasize that deferral is for genuinely intentional issues, not a shortcut.

4. **Under-specification in proposals** — "restructure the hierarchy" without concrete operations. Every proposal option must include specific mutation operations.

5. **Ignoring hints** — the catalog hint is a starting point, not optional. The resolution subagent should follow the hint's guidance and deviate only with reasoning.

---

## Token Estimates

| Component | Tokens |
|---|---|
| System identity (main agent) | ~100 |
| System identity (subagents) | ~50 |
| Turn instructions (bootstrap) | ~150 |
| Turn instructions (main loop) | ~200 (includes ~50 token scope echo) |
| Exploration task prompt | ~150 + findings + context |
| Resolution task prompt | ~100 + findings + entity context |
| Decision review | ~100 + deferred decisions list |

The instructions are deliberately concise. Long instruction blocks get ignored; short ones with clear structure get followed.

---

## Sources

- [ReAct: Reasoning and Acting (Yao et al., ICLR 2023)](https://arxiv.org/abs/2210.03629)
- [Let Me Speak Freely? Format restrictions degrade reasoning (Tam et al., EMNLP 2024)](https://arxiv.org/abs/2408.02442)
- [Drift No More (Oct 2025)](https://arxiv.org/abs/2410.01897) — reminder interventions reduce goal divergence
- [Anthropic: Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Cognitive Design Patterns for LLM Agents](https://arxiv.org/html/2505.07087v2)
