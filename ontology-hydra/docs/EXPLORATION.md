# Exploration Pass

The exploration pass is the second of three passes in each diagnostic round. It receives the ontology, deterministic findings, and the decision registry, and produces contextual findings that require semantic judgment.

For how this fits into the round structure, see [ARCHITECTURE.md](ARCHITECTURE.md) § Round Structure. For the deterministic pass that feeds into exploration, see [CATALOG.md](CATALOG.md). For how findings flow into resolution, see [RESOLUTION.md](RESOLUTION.md).

---

## Purpose

The deterministic pass catches structural problems (graph topology, naming patterns, property counts). The exploration pass catches problems that require *understanding* — is this subClassOf relationship actually is-a? Is this branch an encyclopedia dump? Does this subtree match the stated scope?

**Cost:** Moderate. ~1 LLM call per subtree node explored.

**Output:** Contextual, holistic findings. Open-ended — not tied to a single diagnostic ID. Findings may reference catalog diagnostics (e.g., "confirms T01 candidate on Employee→Company") or be purely exploratory ("this branch conflates sensors and actuators").

---

## Candidate Findings

The deterministic pass produces two types of output:

- **Confirmed findings** — definitively wrong (cycles, dangling references, naming violations). These go straight to resolution.
- **Candidate findings** — flagged by cheap heuristic triggers. The exploration pass investigates and either confirms or dismisses them.

A trigger is a cheap deterministic heuristic that flags a candidate without making a judgment. For example:
- D3.5's trigger: "class has no unique properties, single parent, no children" — deterministic, but whether it *should* become a property requires judgment.
- D3.8's trigger: "sibling name contains parent name while others don't" — pattern detected, but whether it's an abstraction level inconsistency requires semantic evaluation.

The trigger surfaces the candidate; the explorer decides. See [CATALOG.md](CATALOG.md) for which diagnostics have triggers (marked `[trigger]`).

---

## Mechanics: Recursive BFS with Context Propagation

```
explore(node, parent_context, deterministic_findings_for_region)
  → review this node's children as a group
  → informed by: parent_context + deterministic findings in this region
  → produce: findings + summary_context for children
  → for each child subtree worth exploring:
      explore(child, summary_context, ...)
```

The explorer reviews children *as a group* — sibling relationships matter. "Car, Truck, Motorcycle" as siblings under Vehicle is fine; "Car, Truck, RedVehicle" reveals an abstraction level problem that only becomes visible when comparing siblings.

### What the Explorer Receives

For each node being explored:
- The node's children with their property counts and subtree sizes
- Parent context (see § Context Propagation)
- Deterministic findings in this region (e.g., "8 naming violations in this subtree — suggests hasty generation")
- Candidate findings to investigate (e.g., "D3.5 trigger on RedVehicle")
- Relevant decision registry entries (e.g., "global decision: roles modeled as separate classes")

### What the Explorer Produces

For each node:
- **Findings** — problems or gaps discovered. Each has:
  - Description of the issue
  - Affected entities
  - Severity assessment
  - Catalog reference if applicable (e.g., "T01 — is-a overloading")
- **Summary context** — concise framing for children (see § Context Propagation)
- **Candidate verdicts** — for each candidate finding: confirmed, dismissed, or needs-deeper-look

---

## Context Propagation

Each level passes a concise context summary to its children. Not the full transcript — just the relevant framing:

- **Structural observation:** "this branch is large/small relative to siblings"
- **Quality signal:** "parent subtree is well-structured / has issues"
- **Scope note:** "this region may be out-of-scope per requirements"
- **Pattern note:** "sibling subtrees use part-whole modeling; check consistency"

### Concrete Example

**Level 0 (root):** "4 top-level branches: LivingThing (47 classes), Artifact (12), Process (8), Location (3). Heavy imbalance."

**Level 1 (LivingThing):** Receives imbalance context. "Animal has 38, Plant 6, Fungus 3. Animal over-modeled relative to stated scope of 'agriculture'."

**Level 2 (Animal):** Receives over-modeling + scope concern. "Mammal has 25 subclasses with no distinguishing properties — encyclopedia dump. Bird has 8 with distinct properties — well modeled."

Context is cumulative but compressed — each level sees its parent's summary, not the full ancestor chain.

---

## Depth Strategy

| Condition | Behavior |
|---|---|
| Default | Explore top 2–3 levels |
| Findings discovered | Go deeper (drill into problems) |
| Clean assessment, high confidence | Stop — subtree is well-structured |
| Clean assessment, low confidence | Go deeper regardless — large/complex subtree with shallow review |
| Hard cap | 5–6 levels regardless |
| Final round (before stopping) | Full-depth exploration of all subtrees |

The depth strategy is adaptive per subtree. A clean, well-structured branch gets a quick look. A problematic branch gets deep investigation. This focuses LLM calls where they have the most value.

### Confidence-Gated Stopping

The explorer reports *confidence* alongside findings. "This subtree looks well-structured (high confidence)" vs. "I didn't find anything obvious but the subtree is large and I only looked at sibling names (low confidence)." Low confidence triggers deeper exploration regardless of whether findings were produced. This addresses the false-negative risk from hierarchical review — a wrong assessment at level 1 would otherwise cause the system to skip levels 2+.

### Random Deep Probes

Even in "clean" subtrees, ~20% are randomly selected for a full-depth probe each round. If a deep probe finds something the shallow pass missed, that's evidence of a systematic blind spot in that region — the system should increase exploration depth for similar subtrees. This is the capture-recapture idea from the software inspection literature: independent re-inspection estimates missed defect rates.

### Property-Driven Cross-Cuts

Exploration follows not just the class hierarchy but also property connectivity. Classes connected via object properties that span different subtrees are explored together. "Sensor monitors PhysicalQuantity" connects two branches; a problem at that junction is invisible from within either branch. The explorer searches for cross-subtree property connections and evaluates whether the relationship is well-modeled from both ends.

---

## Parallelism

Sibling subtrees are independent once they have parent context. All children of a node can be explored in parallel. The only sequential dependency is parent → children.

```
explore(Vehicle)                     # sequential: must complete first
  ├── explore(GroundVehicle) ──┐
  ├── explore(AerialVehicle) ──┤     # parallel: independent once they have Vehicle's context
  └── explore(WaterVehicle) ───┘
```

This parallelism is a natural property of the BFS structure — no additional coordination needed beyond waiting for parent completion.

---

## What Exploration Catches

Things the deterministic pass misses:

**Taxonomy semantics (requires judgment):**
- T01–T04: is-a overloading (subClassOf → partOf, hasRole, constitutedBy, instanceOf)
- T10: surface-name taxonomy ("GuitarCase subClassOf Guitar")
- T09: polysemous concepts (one class conflating multiple meanings)
- T14: umbrella classes (parent whose children share no genuine common property)
- T13: abstraction level mixing ("MathematicalObject" sibling to "Car")

**Modeling patterns:**
- M04: N-ary relations modeled as binary
- M05: missing reification opportunities
- M07: missing part-whole patterns
- M10: compound names without matching restrictions

**Scope alignment:**
- IA01/IA02: domain mismatch, scope creep
- IA03/IA04: superfluous padding, textbook pattern mismatch
- Coverage gaps — concepts and relationships present in user documents but absent from the ontology

**Holistic assessments:**
- "This subtree is an encyclopedia dump, not a modeled ontology"
- "These siblings classify by different criteria (function vs. material vs. location)"
- "This branch is well-structured — no findings"

### Expansion Through Exploration

The explorer identifies both *problems* and *gaps*. Gaps become findings:
- S05/S08: "these classes are empty shells / this region has no relationships"
- T12: "this branch has 3 classes but the domain warrants 15"
- T06: "this subtree is flat — needs intermediate grouping"
- Coverage: "the requirements mention X but it's absent"

These findings flow through the same resolution pipeline. The fix happens to be additive (expansion) rather than corrective. See [ARCHITECTURE.md](ARCHITECTURE.md) § Overview for the "expansion as emergent fix" principle.

---

## Explorer Tools

The exploration subagent has read-only access to the ontology and domain documents via these tools:

### Ontology Tools

| Tool | What it does |
|---|---|
| `get_class(name)` | Class with description, parents, all data/object properties where it appears in domain or range |
| `get_subtree(root, detail)` | All descendants of a class. `detail="summary"` returns names + property counts; `detail="full"` (default) includes descriptions and property details. Start with summary, drill into full only where needed. |
| `get_property(name)` | Full property details (description, domain, range) |
| `search(query)` | Fuzzy name/description search across classes and properties |
| `get_neighbors(class_name)` | Classes connected via object properties (1-hop graph neighbors) |
| `get_summary()` | The ontology summary (see [SUMMARIZATION.md](SUMMARIZATION.md)) |

### Document Tools

| Tool | What it does |
|---|---|
| `search_documents(query)` | Search document index (summaries) for relevant content. Returns list of (doc_id, title, relevance_snippet). |
| `research_document(doc_id, question)` | Dispatch a document research subagent to read the document and answer a specific question. Returns a concise answer. Result is cached — subsequent calls with the same (doc_id, question) return the cached answer. |

These tools let the explorer drill down from the abstract summary into specific details as needed. The explorer can inspect individual entities, trace connections, search for related concepts, and — critically — check the ontology's coverage against user-provided domain documents.

### Document Research Subagent

The explorer does **not** read full documents directly. Instead, it dispatches a lightweight research subagent with a specific question. This keeps the explorer's context clean and produces focused, cacheable results.

**Why a subagent, not direct reads:**
- **Context hygiene.** A 50-page document dumped into the explorer's context would clutter it with irrelevant detail. The research subagent reads the full document but returns only a concise answer to the specific question.
- **Cacheability.** The subagent's answer is cached by `(doc_id, question)`. If another subtree's exploration needs the same document for a similar question, the cached answer is reused without an additional LLM call. Over the course of a session, the same documents are relevant to multiple subtrees — caching amortizes the cost.
- **Composability.** The research subagent is a simple read-and-answer agent with no tools beyond reading the document. No risk of side effects or tool sprawl.

**Workflow:**

```
Explorer examining the Event subtree:
1. search_documents("events, processes, workflows, admissions")
   → [doc_3: patient_admission_protocol.pdf — "Describes admission workflow..."]

2. research_document(doc_3, "What entities, relationships, and processes
   does this document describe that are relevant to modeling events in
   a hospital ontology?")
   → "Admission events involve: triage (assigning urgency level),
      attending physician assignment, initial lab orders based on
      preliminary diagnosis, result review within 24 hours, possible
      diagnosis revision. Key entities: AdmissionEvent, TriageAssessment,
      LabOrder, Diagnosis. Key relationships: triggers, orderedBy,
      reviewedBy, revisedTo."

3. Explorer compares this against the ontology:
   → Missing: TriageAssessment, LabOrder, diagnosis revision workflow
   → Coverage gap findings generated
```

**Cache behavior:** The cache persists for the session. Cache key is `(doc_id, question_text)`. Questions don't need to be identical for a cache hit — semantic similarity matching (e.g., embedding cosine > 0.9) can reuse prior answers for similar questions. If semantic matching is too complex for v1, exact-match caching still captures the common case (same document researched from different subtrees with the same question template).

**Progressive coverage:** As the system works through different subtrees in different rounds, it naturally reads different documents. Documents about lab tests get researched when exploring the LabTest subtree; documents about departments when exploring Organization. The cache ensures each document is read at most once per question. This grounds coverage gap detection in real domain content instead of LLM training knowledge.

---

## Exploration Journal

The exploration journal is a persistent document that accumulates cross-round observations — things the explorer notices that haven't (yet) become findings. The decision registry captures *decisions*; the journal captures *observations*.

### What Gets Recorded

- **Recurring problem areas:** "The Sensor subtree has been flagged in 3 consecutive rounds — structural issues keep reappearing after fixes."
- **Cross-subtree patterns:** "Documents [3] and [7] describe overlapping concepts (both mention 'assessment workflows') — potential modeling conflict."
- **Coverage notes:** "Document [5] (faculty_handbook.pdf) hasn't been referenced by any exploration yet — may contain unmodeled concepts."
- **Quality signals:** "The Organization branch is consistently clean across rounds — low priority for future exploration."

### Mechanics

- The journal is a single text artifact that persists across rounds as part of session state.
- The explorer *reads* the journal at the start of each exploration and *appends* observations at the end.
- The main agent sees a compact summary of the journal (latest ~5 entries) in the progress report, not the full journal.
- Journal entries are timestamped by round number for provenance.
- No structured format enforced — free-text observations. The value is in accumulating qualitative signal that the deterministic pass and decision registry don't capture.

### Relationship to Decision Registry

The journal and registry serve different purposes:

| | Decision Registry | Exploration Journal |
|---|---|---|
| Records | Decisions (chosen option + reasoning) | Observations (qualitative signal) |
| Trigger | Findings that require resolution | Explorer noticing patterns |
| Consumed by | All passes (suppresses re-raising) | Explorer (informs where to look) |
| Format | Structured (finding, option, reasoning) | Free-text (timestamped notes) |

An observation may eventually *become* a finding (e.g., "the Sensor subtree keeps breaking" → finding about structural instability), but the journal entry itself is not a finding.

---

## Incremental Exploration

On rounds after the first, the exploration pass only re-explores subtrees containing modified entities. The dirty set from incremental re-diagnosis (see [ARCHITECTURE.md](ARCHITECTURE.md) § Incremental Re-Diagnosis) determines which subtrees need re-exploration.

Previously explored clean subtrees are not revisited unless:
- An entity within them changed
- A 1-hop neighbor changed (since neighbor changes can affect semantic judgments)
- The decision registry gained a new global decision that could affect assessment

---

## Exploration vs. Deterministic — Division of Labor

| Aspect | Deterministic Pass | Exploration Pass |
|---|---|---|
| Cost | Cheap (pure computation) | Moderate (~1 LLM call per node) |
| Output | Precise findings with IDs | Contextual, holistic findings |
| Certainty | Zero ambiguity for confirmed; heuristic for candidates | Judgment-based |
| Scope | Single entity or pairwise | Subtree-level, considering siblings and context |
| Catches | Structural violations, naming, metrics | Semantic issues, modeling patterns, gaps |

The passes are complementary. Deterministic findings *inform* exploration: "the deterministic pass flagged 8 naming violations in this subtree, suggesting it was hastily generated." The explorer uses this signal to focus attention.

---

## Open Design Questions

1. **Exploration prompt structure.** Fully open-ended ("review this subtree for quality") vs. checklist-guided ("evaluate: natural partition? similar siblings? appropriate depth? missing groups?") vs. hybrid. Deferred to implementation — will depend on observed quality.

2. **Context propagation format.** Structured fields vs. free-text summary. Structured is more predictable; free-text allows richer nuance. Start with structured, consider free-text if quality is insufficient.
