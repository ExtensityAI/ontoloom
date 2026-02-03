# Ontology Generation Strategies

## Overview

This document outlines a hierarchical approach to ontology generation using a strategist-tactician pattern, where a large model handles global strategy and smaller models execute local tactics.

## The Problem

When generating/refining ontologies iteratively:
- Showing an LLM only a subtree leads to redundancy (it doesn't know what exists elsewhere)
- Showing the full tree is expensive and may exceed context limits
- Structural modifications require global awareness
- Local refinements don't need global context

## Strategist-Tactician Architecture

```
┌─────────────────────────────────────────┐
│  STRATEGIST (large model, full tree)    │
│                                         │
│  Inputs:                                │
│    - Full ontology structure            │
│    - Quality metrics per node           │
│    - History of recent changes          │
│    - High-level goals                   │
│                                         │
│  Outputs:                               │
│    - Prioritized task queue             │
│    - Constraints / guidelines           │
│    - Success criteria per task          │
└──────────────────┬──────────────────────┘
                   │
                   ▼
        ┌──────────┴──────────┐
        ▼          ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │TACTICIAN│ │TACTICIAN│ │TACTICIAN│  (small models, parallel)
   │         │ │         │ │         │
   │ Subtree │ │ Subtree │ │ Subtree │
   │ + task  │ │ + task  │ │ + task  │
   │ + constraints       │ │         │
   └────┬────┘ └────┬────┘ └────┬────┘
        │           │           │
        └───────────┼───────────┘
                    ▼
             ┌─────────────┐
             │  RECONCILER │  (large model)
             │  - Merge    │
             │  - Validate │
             │  - Conflict │
             └─────────────┘
```

## Task Types

| Task | Scope | Needs full tree? | Compute |
|------|-------|------------------|---------|
| "Where is the ontology weak?" | Global | Yes | Light reasoning over structure |
| "Should X be under Y or Z?" | Global | Yes | Needs sibling context |
| "Flesh out properties of Mammal" | Local | No | Dense generation |
| "Add 5 subclasses of Vehicle" | Local | No | Dense generation |

## Strategy Output Format

The strategist emits structured task batches with explicit constraints:

```yaml
task_batch:
  - id: 1
    type: "expand"
    target: "LivingThing > Animal > Mammal"
    guidance: "Focus on marine mammals. We're weak here."
    constraints:
      - "Don't duplicate Cetacean subtree under Fish"
      - "Maintain consistency with existing locomotion properties"
    success_criteria: "At least 3 levels deep, hasMass property on all"

  - id: 2
    type: "refine_properties"
    target: "Vehicle > Aircraft"
    guidance: "Properties are inconsistent with sibling Vehicle subtrees"
    constraints:
      - "Use same property vocabulary as Vehicle > Boat"

  - id: 3
    type: "structural_review"
    targets: ["Tool > CuttingTool", "Weapon > Blade"]
    guidance: "Possible redundancy. Propose merge or differentiation."
```

## Tactician Context

Each tactician receives:
- The relevant subtree (full detail)
- Sibling names (not full structure)
- Ancestor path
- Task specification with constraints
- Global concept index (for deduplication checking)

## Upward Feedback Mechanisms

Tacticians may discover strategic issues. Three options:

### Option 1: Flag and Continue
```yaml
tactician_output:
  changes: [...]
  flags:
    - type: "structural_concern"
      message: "Reptile and Amphibian have overlapping children"
    - type: "scope_exceeded"
      message: "Can't properly define Salamander without seeing Amphibian siblings"
```

### Option 2: Interrupt
Critical discoveries trigger strategic re-evaluation before proceeding.

### Option 3: Autonomy Budget
Tacticians have limited ability to make small structural changes, must flag larger ones.

## Reconciliation

The reconciler handles parallel tactician outputs:
1. Detects conflicts between proposed changes
2. Merges compatible changes
3. Rejects or queues conflicting changes for strategic review
4. Validates global consistency

## Integration with Plan-Review-Implement Cycle

```
PLAN      = Strategist sees full tree, emits task batch
REVIEW    = Human (or large model) validates strategy
IMPLEMENT = Tacticians execute in parallel
RECONCILE = Merge results, feed back to next PLAN
```

## Weighted Sampling for Subtree Selection

The strategist can use multi-objective scoring to prioritize subtrees:

```python
selection_score = (
    thompson_sample(quality)              # Bayesian estimate of node quality
    + c1 * sqrt(log(N) / visits)          # UCB exploration bonus
    + c2 * centrality                     # Structural importance
    + c3 * disagreement                   # Query-by-committee signal
)
```

Metrics to consider:
- **Staleness**: Inverse of visit count
- **Incompleteness**: Missing properties, shallow depth
- **Centrality**: PageRank, betweenness (structural importance)
- **Uncertainty**: Model confidence, committee disagreement
- **Information gain**: Expected entropy reduction from editing

## Relevant Concepts from ML/Statistics

### From Bandits
- **Thompson Sampling**: Maintain distributions over node quality, sample from posterior
- **Contextual Bandits**: Selection policy depends on context (recent changes, domain focus)
- **Non-stationary bandits**: Handle ontology drift with discounted UCB

### From Active Learning
- **Uncertainty sampling**: Prioritize low-confidence nodes
- **Query-by-committee**: Prioritize high-disagreement areas
- **Expected model change**: Prioritize high-impact nodes

### From Information Theory
- **Information gain**: Prioritize edits with highest expected entropy reduction
- **MDL (Minimum Description Length)**: Best ontology compresses domain efficiently
- **Mutual information**: Detect related subtrees for structural review

### From Reinforcement Learning
- **Intrinsic motivation**: Reward exploring novel/unusual states
- **MCTS**: Simulate restructurings, evaluate outcomes
- **Hierarchical RL**: Different policies at different tree levels

### From Graph Theory
- **Centrality measures**: Prioritize structurally important nodes
- **Community detection**: Ensure balanced coverage across subdomains
- **Graph diffusion**: Propagate staleness signals through edges

## Minimal Structured Output

Rather than requiring full JSON/YAML, the strategist can output mostly natural language with minimal structure for subtree references:

```markdown
## Expand marine mammals

@subtree(Animal > Mammal > Cetacean)

This area is sparse compared to terrestrial mammals. Add major families
(Delphinidae, Balaenidae, etc.). Ensure locomotion properties are
consistent with what we have for Fish > CartilaginousFish.

Also check @subtree(Animal > Fish > Marine) for potential overlap.
```

Parsing = one regex for `@subtree(...)`. Maximum flexibility otherwise.

## Ontology Representations for the Strategist

The representation needs to convey:
- Hierarchy (subclassOf structure)
- Properties on each class
- Density/sparseness (where are gaps?)
- Enough detail to spot issues, not so much it overwhelms

### Option A: Indented tree with inline properties

```
Thing
├── LivingThing [hasMass, hasAge]
│   ├── Animal [hasLocomotion, hasHabitat]
│   │   ├── Mammal [gestationPeriod, hasFur]
│   │   │   ├── Primate (3 subclasses)
│   │   │   ├── Cetacean (2 subclasses, sparse)
│   │   │   └── Rodent (12 subclasses)
│   │   └── Reptile [coldBlooded]
│   └── Plant [hasRootSystem]
└── Artifact
    └── Vehicle [maxSpeed, fuelType]
```

**Pros**: Hierarchy is visually obvious, compact
**Cons**: Deep trees get unwieldy, properties clutter the view

### Option B: Hierarchy + separate property table

```
## Hierarchy

Thing
  LivingThing
    Animal
      Mammal
        Primate
        Cetacean
        Rodent
      Reptile
    Plant
  Artifact
    Vehicle

## Properties

| Class | Properties | Count |
|-------|-----------|-------|
| LivingThing | hasMass, hasAge | 2 |
| Animal | hasLocomotion, hasHabitat | 2 |
| Mammal | gestationPeriod, hasFur | 2 |
| Vehicle | maxSpeed, fuelType | 2 |

## Metrics

| Subtree | Depth | Nodes | Props coverage |
|---------|-------|-------|----------------|
| Mammal | 4 | 17 | 85% |
| Reptile | 2 | 3 | 40% |
| Vehicle | 3 | 8 | 90% |
```

**Pros**: Clean separation, metrics surface issues directly
**Cons**: Loses locality (properties far from their classes)

### Option C: Path notation (flat but complete)

```
Thing
Thing > LivingThing                    [hasMass, hasAge]
Thing > LivingThing > Animal           [hasLocomotion]
Thing > LivingThing > Animal > Mammal  [gestationPeriod]
Thing > LivingThing > Animal > Mammal > Cetacean  [marine, echolocation]
Thing > LivingThing > Animal > Mammal > Cetacean > Dolphin  []
...
```

**Pros**: Every node is self-contained, greppable, easy to reference
**Cons**: Verbose, repetitive, loses tree gestalt

### Option D: Compressed with annotations

```
Thing
  LivingThing {2 props}
    Animal {2 props}
      Mammal {2 props} ← 17 descendants
        Primate ← 3 desc
        Cetacean ← 2 desc, SPARSE, low prop coverage
        Rodent ← 12 desc
      Reptile {1 prop} ← SPARSE, 3 desc
    Plant {1 prop}
  Artifact
    Vehicle {2 props} ← 8 desc
```

**Pros**: Hierarchy clear, annotations guide attention, compact
**Cons**: Custom format, annotations could get noisy

### Recommendation

For a strategist that needs to spot issues and assign work, **Option D** (compressed with annotations) or **Option B** (hierarchy + tables) work best. The strategist doesn't need to see every property - it needs to see *where attention is needed*.

## Agentic Strategist

Instead of showing the strategist one fixed view of the entire ontology, give it tools to explore interactively. This allows the strategist to:
- Start with a summary view
- Zoom into areas of interest
- Compare specific subtrees
- Query metrics on demand

### Available Tools

```
get_tree_summary()
    Returns: Compressed hierarchy with annotations (Option D format)

get_subtree(path: str, depth: int = 3)
    Returns: Full detail for a subtree (classes, properties, definitions)
    Example: get_subtree("Animal > Mammal", depth=2)

get_properties(class_name: str)
    Returns: All properties for a class, including inherited

get_metrics(path: str)
    Returns: Depth, node count, property coverage, staleness, etc.

search_classes(query: str)
    Returns: Classes matching name/description pattern

compare_subtrees(path1: str, path2: str)
    Returns: Structural comparison, shared properties, potential overlaps

get_siblings(path: str)
    Returns: Sibling classes with summary info

get_history(path: str)
    Returns: Recent changes to this subtree
```

### Agentic Loop

```
┌─────────────────────────────────────────────────────────┐
│  STRATEGIST (agentic, with tools)                       │
│                                                         │
│  1. Call get_tree_summary() for overview                │
│  2. Identify areas needing attention                    │
│  3. Call get_subtree() / get_metrics() to investigate   │
│  4. Call compare_subtrees() if redundancy suspected     │
│  5. Formulate task batch with full context              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Benefits of Agentic Approach

- **No fixed context size**: Strategist fetches what it needs
- **Adaptive investigation**: Can drill down into problem areas
- **Better decisions**: Sees full detail where it matters, summary elsewhere
- **Handles scale**: Works for small and large ontologies alike
- **Natural workflow**: Mirrors how a human expert would explore

### Example Strategist Session

```
> get_tree_summary()
Thing
  LivingThing {2 props}
    Animal {2 props}
      Mammal {2 props} ← 17 desc
        Cetacean ← 2 desc, SPARSE, low prop coverage    <-- flag
      Reptile {1 prop} ← SPARSE, 3 desc                  <-- flag
    Plant {1 prop}
  Artifact
    Vehicle {2 props} ← 8 desc
    Tool {1 prop}
      CuttingTool ← 4 desc
  ...

> get_metrics("Animal > Mammal > Cetacean")
{
  "depth": 2,
  "node_count": 3,
  "property_coverage": 0.33,
  "staleness": 0.8,
  "last_modified": "2024-01-15"
}

> get_subtree("Animal > Mammal > Cetacean", depth=2)
Cetacean [marine]
  Dolphin []
  Whale []

> get_siblings("Animal > Mammal > Cetacean")
Siblings of Cetacean:
  - Primate (3 subclasses) [opposableThumbs, socialStructure]
  - Rodent (12 subclasses) [incisors, gnawing]
  - Carnivora (8 subclasses) [carnivorous, claws]
  ...

> compare_subtrees("Tool > CuttingTool", "Weapon > Blade")
Overlap analysis:
  - Shared concepts: Knife appears in both
  - Shared properties: hasEdge, hasBlade
  - Recommendation: Consider merging or clarifying distinction

# Strategist now has enough context to emit well-informed tasks
```

### Tradeoff: Latency vs. Quality

Agentic exploration adds latency (multiple tool calls before task emission). Mitigations:
- Cache tool results across strategist sessions
- Precompute metrics and flags
- Allow parallel tool calls
- Set a tool call budget per planning cycle

## Detecting Missing Concepts (External Knowledge)

Internal metrics (depth, property coverage) can't detect what's *absent*. If "Communication" is missing "Email", no flag will fire — the ontology doesn't know what it doesn't know.

### Problem Types

| Problem type | Detection method | Example |
|--------------|------------------|---------|
| Internal quality | Metrics (depth, coverage, staleness) | "Mammal has only 2 subclasses" |
| Missing concepts | External knowledge | "Communication lacks Email" |

### Approaches to Inject Domain Knowledge

#### 1. Reference Ontologies

Compare against existing ontologies:
- schema.org (broad, web-focused)
- DBpedia/Wikidata (encyclopedic)
- Domain-specific standards (FIBO for finance, SNOMED for medicine, etc.)

```
Tool: compare_to_reference(subtree: str, reference: str)

> compare_to_reference("Communication", "schema.org")

Missing in your ontology that exist in schema.org/Communication:
  - EmailMessage
  - SocialMediaPosting
  - SMSMessage
  - VideoChat
```

#### 2. Corpus-Driven Gap Detection

Feed domain text (documents, Wikipedia articles, textbooks) and extract concepts that should exist:

```
Tool: extract_expected_concepts(subtree: str, corpus: str)

> extract_expected_concepts("Communication", corpus="wikipedia_communication")

Concepts frequently mentioned in corpus but missing from ontology:
  - email (487 mentions)
  - instant messaging (234 mentions)
  - video conferencing (189 mentions)
  - newsletter (145 mentions)
```

#### 3. LLM World Knowledge (Explicit Probing)

The model already knows emails exist. Make gap detection explicit:

```
Tool: probe_gaps(subtree: str)

Prompt internally: "Given this subtree, what common real-world
concepts are conspicuously absent?"

> probe_gaps("Communication")

Potentially missing:
  - Digital communication (email, chat, social media)
  - Broadcast media (TV, radio, podcasts)
  - Non-verbal communication (sign language, body language)
```

#### 4. Few-Shot Examples of Good Ontologies

Show what well-developed subtrees look like:

```
Here's a well-structured ontology for Transportation:
  Transportation
    ├── LandTransport
    │   ├── RoadVehicle (car, bus, motorcycle)
    │   ├── RailVehicle (train, tram)
    │   └── HumanPowered (bicycle, walking)
    ├── WaterTransport
    │   ├── Ship
    │   └── Boat
    └── AirTransport
        ├── Airplane
        └── Helicopter

Now evaluate Communication and identify structural gaps.
```

#### 5. Domain Checklists

For specific domains, maintain curated lists:

```yaml
domain: communication
expected_top_level:
  - VerbalCommunication
  - WrittenCommunication
  - DigitalCommunication
  - NonVerbalCommunication

expected_concepts:
  - email
  - letter
  - phone_call
  - video_call
  - sign_language
  ...
```

Checklist violations become flags for the strategist.

### Gap Detection Layer

```
┌─────────────────────────────────────────────────────────┐
│  GAP DETECTION LAYER (runs before strategist)           │
│                                                         │
│  Inputs:                                                │
│    - Current ontology                                   │
│    - Reference ontologies (schema.org, etc.)            │
│    - Domain corpora (optional)                          │
│    - User-provided seeds/expectations                   │
│    - LLM probe results                                  │
│                                                         │
│  Outputs:                                               │
│    - Missing concept suggestions with confidence        │
│    - Source attribution (reference/corpus/LLM/user)     │
│                                                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
              STRATEGIST receives:
                - Ontology summary
                - Internal quality flags
                - External gap suggestions  ← new
```

## Gap Detection via KG Population

Rather than extracting classes from corpus directly (which requires distinguishing classes from instances — a fuzzy problem), use a more grounded approach: try to populate a KG with the corpus data using the current ontology as schema, and observe what doesn't fit.

### The Approach

```
┌─────────────────────────────────────────────────────────┐
│  ONTOLOGY GAP DETECTION VIA KG POPULATION               │
│                                                         │
│  Inputs:                                                │
│    - Current ontology (schema)                          │
│    - Sample corpus / data                               │
│    - User intent (what domain are we modeling?)         │
│                                                         │
│  Process:                                               │
│    1. Attempt to extract entities from corpus           │
│    2. Try to classify each entity under ontology        │
│    3. Try to express relationships using ontology props │
│    4. Collect failures:                                 │
│       - Entities that don't fit any class               │
│       - Relationships that can't be expressed           │
│       - Attributes with no matching property            │
│                                                         │
│  Output:                                                │
│    - Coverage report                                    │
│    - Unclassifiable entities (suggest new classes)      │
│    - Inexpressible relations (suggest new properties)   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Example

**Ontology:**
```
Communication
  └── WrittenCommunication
        └── Letter
```

**Corpus snippet:**
```
"John sent an email to Mary about the quarterly meeting.
She replied via Slack with the budget spreadsheet attached."
```

**Attempted KG population:**
```
Entity: John → Person ✓
Entity: Mary → Person ✓
Entity: email → ??? (no matching class)
Entity: quarterly meeting → ??? (Event? Meeting? nothing fits)
Entity: Slack → ??? (no matching class)
Entity: budget spreadsheet → ??? (Document? Spreadsheet?)

Relation: John -sent-> email → can't express (no Email class)
Relation: email -about-> meeting → can't express
Relation: spreadsheet -attachedTo-> reply → no property for this
```

**Gap report:**
```
Unclassifiable entities:
  - "email" (4 occurrences) - suggest: DigitalCommunication > Email
  - "Slack message" (2 occurrences) - suggest: DigitalCommunication > InstantMessage
  - "meeting" (3 occurrences) - suggest: Event > Meeting
  - "spreadsheet" (1 occurrence) - suggest: Document > Spreadsheet

Inexpressible relationships:
  - "about" (communication about topic) - suggest: hasTopic property
  - "attached" (file attached to message) - suggest: hasAttachment property
```

### Two Variants

**Variant A: Corpus → attempted KG → gaps**
- Start from raw text
- Model extracts entities and relations
- Tries to fit them into ontology
- Reports what doesn't fit

**Variant B: Existing sample KG → coverage analysis**
- You already have some populated data
- Compare data against ontology expressiveness
- "Given this KG and user intent, what can't we represent well?"

Variant B is cleaner if you have data. Variant A works from scratch.

### Why This Is Better Than Direct Class Extraction

| Direct extraction | KG population approach |
|-------------------|------------------------|
| Extract terms, classify as class/instance | Extract entities, try to instantiate |
| Linguistic heuristics (fragile) | Empirical fit (grounded) |
| "Is 'email' a class?" (abstract) | "Can I represent this email?" (concrete) |
| Separate from actual usage | Directly tests schema fitness |

The KG approach answers: **"Can this ontology express this data?"** rather than **"What classes exist in this text?"**

### Incorporating User Intent

User intent focuses the gap analysis:

```
User intent: "Model business communication for a CRM system"

Given this intent, gaps matter differently:
  - "email" not fitting → HIGH priority (core to CRM)
  - "quarterly meeting" not fitting → MEDIUM (relevant)
  - "budget spreadsheet" not fitting → LOW (tangential)
```

The model prioritizes which gaps to surface based on relevance to stated intent.

### Simplified Approach: Direct LLM Prompting

No need to actually build a KG. Just prompt the LLM directly:

```
Prompt:
  Here is an ontology:
  [ontology]

  Here is sample data from the domain:
  [data snippet]

  User intent: [what they're modeling]

  What concepts or relationships in the data cannot be
  expressed with this ontology? Suggest additions.
```

The LLM mentally simulates "can I represent this?" without building infrastructure.

### When to Run Gap Analysis

| Trigger | When | Tradeoff |
|---------|------|----------|
| **Bootstrap** | Once at start | Gets initial direction, no ongoing cost |
| **Periodic** | Every N cycles | Catches drift, but may be wasteful |
| **On plateau** | When internal metrics stop improving | Efficient, needs plateau detection |
| **On new data** | When user provides more sample data | Reactive, user-driven |
| **Strategist-triggered** | When strategist suspects gaps | Requires agentic strategist |

### Recommended Flow

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  BOOTSTRAP (once)                                       │
│    - User provides intent + sample data                 │
│    - Run gap analysis                                   │
│    - Initialize task queue                              │
│                                                         │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  MAIN LOOP                                              │
│    1. Strategist plans (internal flags only)            │
│    2. Tacticians execute                                │
│    3. Reconcile                                         │
│    4. Check: plateau? new data? N cycles?               │
│         → If yes: re-run gap analysis                   │
│    5. Loop                                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Gap analysis is **expensive** (large model + full ontology + data), so don't run every cycle. Run it:

1. **At start** - to bootstrap direction
2. **When stuck** - internal refinement has diminishing returns
3. **When data changes** - new sample data reveals new gaps

### Plateau Detection

Simple heuristic:

```python
if last_N_cycles_changed < threshold:
    # internal refinement is saturating
    trigger_gap_analysis()
```

Or track a quality metric and trigger when it flattens.

### Integration with Strategist

```
┌──────────────────────────────────────────────────────────┐
│  GAP ANALYSIS (runs occasionally)                        │
│                                                          │
│  Input: ontology + sample data + user intent             │
│  Output: missing classes, missing properties             │
│                                                          │
│  Triggers:                                               │
│    - Initial bootstrap                                   │
│    - Every N cycles                                      │
│    - Internal metrics plateau                            │
│    - New sample data provided                            │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  STRATEGIST (runs every cycle)                           │
│                                                          │
│  Input:                                                  │
│    - Ontology summary                                    │
│    - Internal quality flags                              │
│    - Gap analysis results (when available)  ← cached    │
│                                                          │
│  Output: task batch                                      │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

Gap analysis results get cached and fed to strategist until next gap analysis runs.

## Design Considerations: Structured vs. Natural Language Output

### Tradeoffs

| Format | Generation | Parsing |
|--------|------------|---------|
| Markdown | Easy, forgiving | Hard, needs heuristics or LLM |
| JSON | Error-prone (syntax) | Trivial, deterministic |

### For Autonomous Loops

Two options for reliable round-tripping:

**Option 1: Structured output modes**
- Anthropic: Tool use with schema
- OpenAI: `response_format: { type: "json_schema", schema: ... }`

These guarantee valid JSON — no syntax errors possible.

**Option 2: Markdown → LLM parser**
```
Strategist (large) → Markdown
                          ↓
               Parser (small/cheap) → JSON
                          ↓
               Tacticians receive JSON + original prose
```

### Recommendation

If API supports structured output: use JSON with a schema.
If not: markdown with a cheap parsing model.

Worst option: asking for JSON without structured output mode (syntax errors, retry logic needed).

## Agentic vs. Fixed View: When to Use What

### Case Against Agentic Strategist

- **Complexity**: More code to build and maintain
- **Latency**: Multiple round-trips before work starts
- **Cost**: Each tool call is an LLM generation
- **Exploration quality**: Strategist might explore poorly
- **Debugging**: Harder to trace what strategist saw

### Alternative: Pre-computed Flags + Fixed View

```
SYSTEM (deterministic, cheap):
  - Compute metrics for all nodes
  - Flag issues: sparse, stale, low coverage, potential overlaps
  - Generate summary view with flags

STRATEGIST (single call, no tools):
  - Receives summary + flags
  - Prioritizes and assigns tasks
```

### When Agentic is Actually Better

- Very large ontologies (can't fit summary in context)
- Subtle issues requiring reasoning to detect
- Comparison tasks ("Are these redundant?")
- Unknown unknowns (anticipated flags miss novel issues)

### Recommendation

Start simple (fixed view + flags). Add tools incrementally:

1. Start: Summary view with flags, single strategist call
2. If strategist lacks context: Add `get_subtree()`
3. If redundancy detection poor: Add `compare_subtrees()`
4. If ontology outgrows context: Add pagination

Build minimal thing first, extend based on actual failures.

## Termination Criteria

When is the ontology "done"? Options:

### Fixed Budget
- Stop after N cycles
- Stop after N tokens/dollars spent
- Simple but arbitrary

### Convergence
- Stop when changes per cycle drop below threshold
- Stop when quality metrics plateau
- Risk: local optimum

### Coverage-Based
- Stop when gap analysis returns no high-priority missing concepts
- Stop when sample data achieves X% coverage
- Requires good gap detection

### User-Defined Goals
- User specifies: "I need at least 3 levels under Communication"
- System stops when goals are met
- Most aligned with actual needs

### Practical Approach
```python
stop_if:
  - changes_last_3_cycles < 5 AND
  - gap_analysis_high_priority == 0 AND
  - (user_goals_met OR cycles > max_cycles)
```

## Quality Metrics

How to measure ontology quality:

### Structural Metrics
- **Depth**: Average/max depth of tree
- **Breadth**: Average children per node
- **Balance**: Variance in subtree sizes
- **Orphans**: Nodes with no properties or children

### Coverage Metrics
- **Property coverage**: % of classes with at least N properties
- **Definition coverage**: % of classes with descriptions
- **Leaf ratio**: % of nodes that are leaves (too high = shallow)

### Consistency Metrics
- **Property coherence**: Do siblings use similar property vocabularies?
- **Naming consistency**: CamelCase vs snake_case, singular vs plural
- **Redundancy score**: Detected overlaps between subtrees

### External Metrics
- **Reference alignment**: Overlap with schema.org, Wikidata, etc.
- **Data coverage**: % of sample data expressible
- **User goal completion**: % of stated requirements met

### Composite Score
```python
quality = (
    w1 * structural_balance +
    w2 * property_coverage +
    w3 * data_coverage +
    w4 * consistency_score
)
```

## Consistency Checking

Ensure logical consistency:

### Name Collisions
- Same class name in different subtrees
- Same property name with different semantics
- Detection: simple string matching

### Circular Dependencies
- A isA B isA A (invalid)
- Detection: cycle detection in graph

### Property Domain/Range Violations
- Property defined on parent, misused on child
- Detection: type checking

### Disjointness Violations
- If Mammal and Reptile are disjoint, nothing can be both
- Detection: requires explicit disjointness constraints

### LLM-Based Consistency
```
Prompt:
  Review this ontology for logical inconsistencies:
  [ontology]

  Check for:
  - Concepts that seem misplaced
  - Properties that don't make sense for their classes
  - Redundant or contradictory classifications
```

## Handling Cross-Cutting Concerns

Some concepts span multiple branches:

**Problem**: "Digital" applies to Communication, Commerce, Art, Education...

### Option 1: Multiple Inheritance
```
DigitalCommunication
  isA: Communication
  isA: DigitalThing
```
Requires: ontology supports multiple parents

### Option 2: Mixins / Traits
```
DigitalThing (mixin)
  properties: hasFileFormat, hasDataSize

Email
  isA: Communication
  hasMixin: DigitalThing
```

### Option 3: Properties Instead of Classes
```
Email
  isA: Communication
  isDigital: true
```
Simpler but loses structure

### Option 4: Faceted Classification
Separate orthogonal dimensions:
- By medium: Digital, Physical, Verbal
- By purpose: Personal, Business, Marketing
- By format: Text, Audio, Video

Class = intersection of facets

### Recommendation
Start with single inheritance (tree). When cross-cutting concerns emerge, add properties. Only move to multiple inheritance if property approach becomes unwieldy.

## Bootstrapping Strategies

How to start from nothing:

### Top-Down
1. User provides high-level categories
2. System expands each category
3. Iterate deeper

```
User: "I need an ontology for vehicles"
System: Creates Vehicle > {Land, Water, Air}
Next cycle: Expands each...
```

### Bottom-Up
1. User provides example instances
2. System clusters and abstracts
3. Build hierarchy from clusters

```
User: "car, truck, bicycle, boat, airplane"
System: Clusters → {car, truck, bicycle} = LandVehicle, etc.
```

### Seed + Expand
1. Start with reference ontology subset
2. Customize and expand from there

```
System: Imports schema.org/Vehicle subtree
User: "Add more detail for electric vehicles"
```

### Intent-Driven
1. User describes intent
2. LLM generates initial structure
3. Refine from there

```
User: "Ontology for a car dealership inventory system"
LLM: Generates Vehicle hierarchy + properties like price, mileage, condition
```

## Versioning and Rollback

Handle bad changes:

### Simple: Linear History
```
v1 → v2 → v3 → v4
              ↑
          rollback target
```
Store full ontology at each version. Rollback = restore snapshot.

### Efficient: Delta Storage
Store only changes between versions:
```
v1: full ontology
v2: +added Cetacean, -removed OldClass, ~modified Mammal.props
v3: +added Dolphin under Cetacean
```

### Branch and Merge
For experimental changes:
```
main: v1 → v2 → v3
              \
experimental:  → v2a → v2b
                        ↓
                    merge back?
```

### Automatic Rollback Triggers
```python
if quality_score(new_version) < quality_score(old_version) - threshold:
    rollback()
    flag_for_review()
```

## Evaluation Against Gold Standards

If you have a reference ontology:

### Precision/Recall
- **Precision**: Of classes you generated, how many are in reference?
- **Recall**: Of classes in reference, how many did you generate?

### Structural Similarity
- Tree edit distance
- Graph kernel similarity
- Embedding-based similarity (embed both, compare)

### Semantic Similarity
- Do class names/descriptions mean the same thing?
- Use LLM to judge equivalence

### Practical Use
- Reference as soft target, not hard requirement
- Alert when drifting far from reference
- Use for benchmarking improvements
