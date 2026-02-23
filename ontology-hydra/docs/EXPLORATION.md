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
| Nothing found at a level | One more level as sanity check, then stop |
| Hard cap | 5–6 levels regardless |

The depth strategy is adaptive per subtree. A clean, well-structured branch gets a quick look. A problematic branch gets deep investigation. This focuses LLM calls where they have the most value.

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
- Coverage gaps — "the requirements mention X but the ontology doesn't have it"

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

The exploration subagent has read-only access to the ontology via these tools:

| Tool | What it does |
|---|---|
| `get_class(name)` | Class with description, parents, all data/object properties where it appears in domain or range |
| `get_subtree(root)` | All descendants of a class with their properties |
| `get_property(name)` | Full property details (description, domain, range) |
| `search(query)` | Fuzzy name/description search across classes and properties |
| `get_neighbors(class_name)` | Classes connected via object properties (1-hop graph neighbors) |
| `get_summary()` | The ontology summary (see [SUMMARIZATION.md](SUMMARIZATION.md)) |

These tools let the explorer drill down from the abstract summary into specific details as needed. The explorer can inspect individual entities, trace connections, and search for related concepts.

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
