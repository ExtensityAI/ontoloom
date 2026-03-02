# Future Ideas

Things to consider but not part of the initial implementation. Organized by feasibility and expected value.

---

## Near-Term Extensions

### Post-Generation Iteration

Currently, each generation is a single session. If the user receives the ontology and disagrees with the result, they start a new session with adjusted intent/documents.

A resume capability would allow the user to provide feedback ("this is wrong about X") and re-enter the diagnostic loop with the decision registry intact. This requires:
- Persisting session state (snapshots, registry, document index) across sessions
- A "correction" bootstrap that takes the completed ontology + user feedback as input
- Injecting user feedback as new findings or scope document amendments

**Why deferred:** The per-session model is sufficient for v1. Post-generation iteration adds cross-session persistence complexity. Add when users report that re-running from scratch is too expensive for minor corrections.

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

### Voting for Phase 1 Structural Decisions

For the highest-stakes structural decisions (Phase 1), run 2–3 independent resolution attempts and pick the best. Each attempt sees the same findings but produces proposals independently — differences reveal where the "obvious" answer isn't obvious.

**Why Phase 1 only:** Phase 1 decisions have the largest blast radius (top-level hierarchy, scope alignment) and the Phase 1 round cap is small (3 rounds), so the cost is bounded. Phase 2 processes per-subtree with many more decisions — voting there would be prohibitively expensive.

**When to add:** If practice shows that Phase 1 structural decisions frequently need reversal in later phases, voting is cheaper than reversal. If Phase 1 decisions are generally stable, this isn't worth the cost.

### Document Clustering for Large Document Sets

For extremely large document sets (500+), cluster documents by content similarity and sample representatives from each cluster for bootstrap deep reads. This turns an O(N) bootstrap read cost into O(K) where K is the number of clusters.

**Approach:**
- Embed document summaries (from the index, which is always built in full)
- Cluster by embedding similarity
- Sample 1–2 documents per cluster for bootstrap deep reads, weighted by cluster size and intent relevance
- During the main loop, the research subagent still accesses any document on demand — clustering only affects bootstrap prioritization

**Why deferred:** The current architecture handles up to ~200 documents fine (index-building is cheap and parallelizable, deep reads are on-demand via research subagent). Clustering adds an embedding model dependency. Add only if the system is actually used with 500+ document sets — at that scale, the use case is closer to corpus analysis than domain document processing.

### Evaluation Harness

Build a small set of reference ontologies (3–5 domains) with known-good structures and known planted defects. Use them to test whether the diagnostic pipeline catches problems and whether fixes actually improve quality.

**Components:**
- Reference ontologies with annotated defects (e.g., "T01 at Employee→Company", "S03 at Vehicle with 25 children")
- Expected finding sets for each reference
- Quality metrics before/after resolution
- Regression tests: does a new diagnostic or prompt change degrade performance on known cases?

**Not a runtime feature** — a development/testing tool. The equivalent of a test suite for the diagnostic pipeline itself.

### Decision Dependency Graph

Track which decisions cite other decisions as context — e.g., "chose option B for T01 on Employee because of the global decision to model roles as subclasses." When an upstream decision is questioned, all downstream dependents surface automatically, giving blast-radius visibility for any potential reversal.

**Why deferred:** The phase system with intra-phase reversibility ordering and per-subtree advancement (see [RESOLUTION.md](RESOLUTION.md) § Fix Ordering) already reduces the risk of costly reversals. The exploration pass and diagnostic system catch most bad structural decisions within 1–2 rounds before deep entanglement. Add dependency tracking if practice shows that late-discovered bad decisions are a real problem, not just a theoretical one.

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

### Change Strategies for Decision Reversal

When a structural decision turns out wrong, the ontology evolution literature (Stojanovic 2004; Flouris 2006; Djedidi & Aufaure 2010) strongly favors **minimal change over rebuilds**. Strategies ranked from cheapest to most expensive:

1. **Atomic change with automatic propagation.** Apply the reversal as a single mutation operation; let the mutation API cascade references. Already supported — this is what the mutation API does.
2. **Pattern-based resolution.** The reversed decision maps to an ODP (see [PATTERNS.md](PATTERNS.md)); apply the pattern template. Already supported — this is what the resolution pass does with pattern hints.
3. **Minimal contraction.** Find the smallest set of axioms/assertions to remove or modify to undo the decision's effects. Based on AGM belief revision theory (Flouris et al. 2008). Not yet implemented but bounded in scope.
4. **Diff-based adaptation with invertible operations.** Track forward/reverse diffs for each round (COnto-Diff, Hartung et al. 2013). Rollback = apply reverse diffs in order. Requires invertible mutation operations — the mutation API partially supports this already via its diff returns.
5. **Version rollback with selective replay.** Roll back to a checkpoint before the bad decision, then selectively replay only the good decisions made after it. Requires ontology snapshots (already persisted) + decision registry (already tracked). Not yet implemented but the infrastructure exists.
6. **Full subtree rebuild.** Detach the affected subtree, re-bootstrap it with corrected constraints, reattach. Last resort — expensive and only viable when the subtree has clean boundaries.

**Current state:** Strategies 1–2 are already available through the mutation API and resolution pass. Strategies 3–5 are implementable with existing infrastructure if needed. Strategy 6 is deferred unless practice shows the cheaper strategies are insufficient.

**Snapshots:** Already persisted after each round. Automated rollback on diagnostic regression is not yet implemented but the persistence model supports it.

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
