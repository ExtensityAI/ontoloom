# Future Ideas

Things to consider but not part of the initial implementation.

## Knowledge Graph Diff as Validation

Use the ontology to extract a knowledge graph from sample data, then diff the KG before and after a modification. If the new ontology doesn't extract any additional or more useful information, the modification may not have been worthwhile.

Approach:
- Before modification: extract KG from data using current ontology
- After modification: extract KG from same data using new ontology
- Diff the two KGs
- If no new triples or no more specific triples → the change didn't add representational value
- Could serve as a signal to the agent that a modification was low-value or that a subtree is over-specified

This is a functional evaluation (vs. structural diagnostics). It answers "can the ontology actually represent more?" rather than "is the ontology well-formed?"

Open questions:
- Where does the sample data come from? User-provided? Synthetic? Web-scraped from the domain?
- How expensive is KG extraction per modification?
- Is this a diagnostic (automatic) or an action the agent can invoke?
- Could this replace or complement the stopping condition? ("No more extractable information" = done)

## LLM-Powered Property Recommendations

Use a lightweight model to analyze properties and recommend OWL characteristics that should be set — transitivity, symmetry, reflexivity, functionality, inverse functional, etc. For example:

- `isPartOf` → should probably be transitive
- `hasParent` → should probably have an inverse (`isParentOf`)
- `hasSSN` → should probably be functional (one value per individual)

This could be a diagnostic tier or part of the modification subagent's output. Cheap to run with a small model since it's just analyzing property names and descriptions one at a time.

Note: the model currently has `inverse_of` commented out as a future feature. These recommendations would become more actionable as the model gains more OWL expressivity.

## Modification Subagent Recommendations

The subagent report format already includes `recommendations`, `ambiguities_found`, and `conflicts_detected` fields (see AGENT_MEMORY.md § Subagent Report Format). The infrastructure for subagents to feed strategic intelligence back to the main agent exists — the question is whether to actively prompt for it.

Actively prompting the modification subagent to generate recommendations ("what else did you notice?") could surface issues the main agent wouldn't see from the abstract summary:
- "While adding sensor subtypes, I noticed the `monitors` property has a very broad range — consider narrowing it"
- "The Component hierarchy might benefit from a Mechanical/Electrical split"
- "Class X has no properties and may need attention"

The main agent can add these as plan tasks, investigate, or ignore them. Worth testing whether the quality of recommendations justifies the extra tokens in the subagent prompt.

## Diagnostic Prioritization (Layer 2)

Treat diagnostic selection as a multi-armed bandit problem. Over time, learn which diagnostics actually lead to useful fixes (high reward) vs. which are almost always suppressed (low reward).

Approach:
- Track per diagnostic type: times raised, times fixed, times suppressed
- Compute a priority score from the fix/suppress ratio
- Use epsilon-greedy sampling: focus on high-priority diagnostics but still sample low-priority ones occasionally
- Could also factor in fix cost (how many turns did it take to resolve?)

This makes the agent more efficient over multiple runs — it learns which checks are worth paying attention to for a given domain.

## A/B Testing for Modeling Decisions

When the agent is unsure between two modeling approaches, it can run both and compare:

1. Branch the ontology
2. Apply approach A to one branch, approach B to the other
3. Extract KGs from sample data using both
4. Compare which KG is richer / more useful
5. Pick the winner, discard the other

Expensive (two modification cycles + two KG extractions) but valuable for genuinely ambiguous decisions. Could be implemented as a skill: "When unsure between two modeling approaches, run this comparison procedure."

Depends on the KG diff infrastructure (see "Knowledge Graph Diff as Validation" above).

## Loop Detection

Flag when the agent calls the same tool with similar arguments 2-3 consecutive times within an inner loop. This is ReAct's most common failure mode — repetitive stuck behavior. LangGraph's RFC formally identified it as a fundamental reliability gap and proposes loop detection after 3 similar steps with progress assessment every 2 steps.

Implementation:
- Track `(action_type, target/scope)` tuples within the inner loop
- If the same tuple appears 2-3 times consecutively, inject a warning: "You've dispatched similar actions N times. Consider a different approach or ask_user."
- Could also detect semantic similarity (not just exact match) for cases where the agent rephrases slightly

The step countdown (`[Step N/10]`) already addresses budget blindness. Loop detection catches a different failure: the agent has budget left but is going in circles.

## Action Log Compaction

The action log is append-only and grows at ~25 tokens per outer turn. At turn 100, this is ~2,500 tokens — a significant chunk of context. Early log entries also fall in the "Lost in the Middle" attention blind spot.

When this becomes a problem, consider a hybrid approach:
- Keep the most recent ~10 turns as raw one-line entries
- Summarize earlier turns into a compact paragraph (~200-300 tokens) covering: major milestones, key user decisions, completed plan tasks
- Re-summarize periodically (every 20 turns or when raw section exceeds threshold)

This preserves trajectory awareness while capping log growth. The raw recent entries maintain the agent's sense of momentum; the summary preserves strategic context.

**Trigger for adding this:** action log exceeds ~1,500 tokens (~60 turns) or the agent demonstrably ignores early log entries.

## Workspace Files & Reversible Compaction

If the `notes` field becomes a bottleneck — either because the agent spends too many tokens rewriting notes, or because findings are too large to summarize effectively — add file-based persistence for subagent reports.

**The pattern (reversible compaction):** if information exists in the environment (a file), strip it from context and keep only a reference. The content is recoverable, not lost.

Concretely:
- Subagent reports get persisted to workspace files organized by turn (`workspace/turn-N/explore-tX.json`)
- Plan tasks get an `output_refs: []` field — the system appends report file paths as subagents complete
- Full reports are replaced in the prompt by one-line summaries with file references
- Agents get `read_file(path)` and `list_files()` tools to access old reports on demand
- Modification subagent additionally gets `write_file(path, content)` for intermediate artifacts

**Trigger for adding this:** the agent frequently re-explores things it already explored (notes were insufficient), or the agent spends a large fraction of its actions on `plan_update` notes rewrites. Track both metrics during testing.

**Additional context optimizations to consider alongside:**
- KV-cache-aware prompt construction: stable items (system identity, scope doc) at top, volatile items at bottom. Avoid dynamic tool list changes between phases (mask instead of remove). Deterministic serialization for all prompt sections.
- Inner loop context compaction: lossy summarization of older observations when context pressure is high within a single turn.
- Lossy summarization of the full prompt at ~128K tokens (triggered well before the advertised context limit, since performance degrades earlier). Keep the most recent tool calls in raw format to preserve the model's "rhythm."
