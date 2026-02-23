# Future Ideas

Things to consider but not part of the initial implementation. Organized by feasibility and expected value.

---

## Near-Term Extensions

### Model Expansion: Restrictions and Axioms

The current model covers ~55-60% of the diagnostic catalog. Adding support for OWL constructs would unlock the remaining checks:

- **Restrictions** (someValuesFrom, allValuesFrom, cardinality) — enables R01–R22, the restriction anti-pattern checks
- **Equivalence class definitions** — enables E01–E06, the equivalence traps
- **Property characteristics** (functional, symmetric, transitive) — enables P09, P10, P20
- **Disjointness axioms** — enables T08, the most impactful missing check

The checker interface is designed to be axiom-agnostic (see [ARCHITECTURE.md](ARCHITECTURE.md) § Scope), so adding checkers for new constructs is incremental — no architecture changes needed.

### LLM-Powered Property Recommendations

Use a lightweight model to analyze properties and recommend OWL characteristics:

- `isPartOf` → should probably be transitive
- `hasParent` → should probably have an inverse (`isParentOf`)
- `hasSSN` → should probably be functional

Cheap to run since it's analyzing property names and descriptions one at a time. Becomes more actionable as the model gains expressivity (currently `inverse_of` is the only characteristic field).

Could be a diagnostic category or part of the resolution subagent's output.

### Subagent Recommendations

The resolution subagent report format includes `recommendations` and `ambiguities_found` fields. Actively prompting it to generate recommendations ("what else did you notice while fixing this?") could surface issues invisible from the abstract summary:

- "While fixing sensor properties, I noticed the `monitors` property has a very broad range — consider narrowing it"
- "The Component hierarchy might benefit from a Mechanical/Electrical split"

These feed back to the main agent as new candidate findings. Worth testing whether quality justifies the extra tokens.

---

## Medium-Term Features

### Knowledge Graph Diff as Validation

Use the ontology to extract a knowledge graph from sample data, then diff the KG before and after a modification. If the new ontology doesn't extract more or more useful information, the modification may not have been worthwhile.

**Approach:**
1. Before modification: extract KG from data using current ontology
2. After modification: extract KG from same data using new ontology
3. Diff the two KGs
4. If no new triples or no more specific triples → the change didn't add representational value

This is a **functional** evaluation (vs. structural diagnostics). It answers "can the ontology actually represent more?" rather than "is the ontology well-formed?"

**Open questions:**
- Where does the sample data come from? User-provided? Synthetic? Web-scraped?
- How expensive is KG extraction per modification?
- Could this replace or complement the stopping condition? ("No more extractable information" = done)

### Diagnostic Prioritization (Bandit)

Treat diagnostic selection as a multi-armed bandit problem. Over time, learn which diagnostics lead to useful fixes (high reward) vs. which are almost always deferred (low reward).

**Approach:**
- Track per diagnostic type: times raised, times fixed, times deferred
- Compute priority score from fix/defer ratio
- Use epsilon-greedy: focus on high-priority diagnostics, occasionally sample low-priority ones
- Factor in fix cost (how many tokens / calls to resolve?)

Makes the system more efficient over multiple runs — it learns which checks matter for a given domain type.

### A/B Testing for Modeling Decisions

When the system is unsure between two modeling approaches:

1. Branch the ontology
2. Apply approach A to one branch, approach B to the other
3. Run diagnostics on both
4. Compare which produces fewer findings / better metrics
5. Pick the winner, discard the other

Expensive (two resolution cycles) but valuable for genuinely ambiguous decisions. Depends on efficient ontology snapshotting (already supported — see [ARCHITECTURE.md](ARCHITECTURE.md) § Persistence).

### Loop Detection

Flag when the resolution pass produces fixes that introduce the same problems they're fixing — the classic oscillation pattern.

**Implementation:**
- Track `(diagnostic_id, affected_entities)` tuples across rounds
- If the same tuple appears in rounds N and N+2, after being "resolved" in N+1, inject a warning
- Could also detect semantic similarity for cases where the finding is slightly different but structurally the same

The convergence check (see [ARCHITECTURE.md](ARCHITECTURE.md) § Round Structure) catches the macro pattern (more findings than before). Loop detection catches the micro pattern (specific findings cycling).

---

## Long-Term / Research

### Embedding-Based Checks

Use embedding similarity for semantic duplicate detection, domain vocabulary mismatch, and coverage assessment:

- D03/D04/D07: semantic duplicate classes/properties (embedding distance < threshold)
- IA01: domain vocabulary mismatch (embedding centroid outlier detection)
- Coverage: embedding-space gaps where concepts should exist

**Why deferred:** Requires an embedding model in the pipeline, adds latency and cost, and the LLM exploration pass catches most of these already. Add when the exploration pass proves insufficient for duplicate/coverage detection.

### Reasoner Integration

Run an OWL reasoner (HermiT, ELK) to find unsatisfiable classes, diff asserted vs. inferred hierarchy, and check profile compliance.

**Not applicable with current model** — no axioms, no restrictions, nothing for a reasoner to work with. Becomes critical if the model gains OWL expressivity.

Every peer system (NeOn-GPT, LLMs4Life, Ontogenia) includes reasoner validation. The architecture should plan for this even though it's not needed yet.

### Ontology Checkpointing and Rollback

Snapshots are already persisted after each round, but automated rollback on diagnostic degradation is not implemented. Consider:

- "If critical diagnostic count increased after a round, offer a rollback option"
- "If the KG diff (see above) shows representational regression, auto-rollback"
- Branching: keep the pre-fix snapshot alive until the next round confirms the fix didn't cause regression

### Action Log Compaction

The progress report grows linearly. At round 100, ~2,500 tokens. When this becomes a problem:

- Keep the most recent ~10 rounds as raw entries
- Summarize earlier rounds into a compact paragraph (~200-300 tokens)
- Re-summarize periodically

**Trigger:** Progress report exceeds ~1,500 tokens (~60 rounds).

### Workspace Files & Reversible Compaction

If findings become too large to summarize effectively in the progress report, add file-based persistence:

- Full reports persisted to workspace files organized by round
- Progress report contains one-line summaries with file references
- Subagents get `read_file(path)` tool to access old reports on demand

**The pattern (reversible compaction):** if information exists in the environment (a file), strip it from context and keep only a reference. The content is recoverable, not lost.

**Trigger:** The system frequently re-explores things it already explored (progress report was insufficient for context).

### KV-Cache Optimization

Several techniques to maximize KV-cache hit rates:

- **Stable items at top:** System identity, scope document (rarely change) at prompt positions 1-2
- **Deterministic serialization:** All prompt sections serialize identically across rounds (see [ARCHITECTURE.md](ARCHITECTURE.md) § Persistence & Serialization)
- **Mask instead of remove:** If a tool or capability is temporarily unavailable, mask it rather than removing it from the prompt (avoids cache invalidation)
- **Inner loop compaction:** Lossy summarization of older observations when context pressure is high within a single round

### Cross-Session Learning

Currently the decision registry is per-session. Cross-session persistence could enable:

- Learning domain-specific patterns ("in healthcare ontologies, always model roles separately")
- Reusing scope decisions ("last time we excluded facilities, do it again?")
- Diagnostic tuning (bandit model carries over)

Requires careful design to avoid stale decisions polluting new sessions.

---

## Coverage Gaps in Diagnostic Catalog

Areas where the current catalog (see [CATALOG.md](CATALOG.md)) has known gaps:

| Area | Current Coverage | Gap |
|---|---|---|
| Pattern-based anti-patterns | ~95% | Covered well |
| Reasoner-based checks | ~40% | Needs reasoner integration |
| Completeness/coverage | ~30% | Needs KG diff or competency questions |
| Queryability | ~20% | Needs SPARQL pattern analysis |
| LLM-specific patterns | ~90% | Covered well |

Addressing these gaps would move total diagnostic coverage from ~55-60% to ~85-90% of the full catalog.
