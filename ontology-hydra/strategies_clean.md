# Ontology Generation Strategies

## Architecture Overview

```
┌─────────────────────────────────────────┐
│  STRATEGIST (large model)               │
│  - Sees full ontology (summary view)    │
│  - Receives quality flags + gap analysis│
│  - Emits prioritized task batch         │
└──────────────────┬──────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼          ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │TACTICIAN│ │TACTICIAN│ │TACTICIAN│  (small models, parallel)
   │ Subtree │ │ Subtree │ │ Subtree │
   │ + task  │ │ + task  │ │ + task  │
   └────┬────┘ └────┬────┘ └────┬────┘
        └───────────┼───────────┘
                    ▼
             ┌─────────────┐
             │  RECONCILER │
             │  Merge/validate/conflict
             └─────────────┘
```

## Main Loop

```
BOOTSTRAP:
  1. User provides intent + sample data
  2. Run gap analysis
  3. Initialize task queue

LOOP:
  1. Strategist plans (summary + flags + cached gap results)
  2. Tacticians execute in parallel
  3. Reconciler merges results
  4. If plateau or new data: re-run gap analysis
  5. If termination criteria met: stop
```

## Strategist

### Input
- Ontology summary (compressed tree with annotations)
- Internal quality flags (sparse, stale, low coverage)
- Gap analysis results (missing concepts from external knowledge)

### Output Format
Natural language with subtree markers:
```markdown
## Expand marine mammals

@subtree(Animal > Mammal > Cetacean)

This area is sparse. Add major families (Delphinidae, Balaenidae).
Ensure consistency with Fish > Marine locomotion properties.
```

### Ontology Representation
```
Thing
  LivingThing {2 props}
    Animal {2 props}
      Mammal {2 props} ← 17 desc
        Cetacean ← 2 desc, SPARSE, low prop coverage
      Reptile {1 prop} ← SPARSE
    Plant {1 prop}
  Artifact
    Vehicle {2 props} ← 8 desc
```

### Optional Tools (for large ontologies)
- `get_tree_summary()` - compressed overview
- `get_subtree(path, depth)` - full detail for a subtree
- `get_metrics(path)` - depth, coverage, staleness
- `compare_subtrees(path1, path2)` - overlap analysis

## Tactician

### Input
- Subtree (full detail)
- Sibling names (not full structure)
- Ancestor path
- Task + constraints
- Global concept index (for dedup)

### Output
```yaml
changes:
  - type: add_class
    path: "Animal > Mammal > Cetacean > Dolphin"
    properties: [echolocation, podSize]
  - type: add_property
    class: "Cetacean"
    property: "hasBlowhole"

flags:
  - type: "structural_concern"
    message: "Cetacean overlaps with Marine concept"
```

## Gap Analysis

### When to Run
- Bootstrap (once at start)
- On plateau (internal metrics stop improving)
- On new sample data

### Method
Prompt LLM with ontology + sample data + user intent:
```
Here is an ontology: [ontology]
Here is sample data: [data]
User intent: [intent]

What concepts or relationships in the data cannot be expressed?
```

## Quality Metrics

### Internal
- Depth/breadth balance
- Property coverage (% classes with properties)
- Definition coverage
- Naming consistency

### External
- Reference alignment (schema.org, Wikidata)
- Sample data coverage
- User goal completion

## Termination Criteria

```python
stop_if:
  - changes_last_3_cycles < threshold AND
  - gap_analysis_high_priority == 0 AND
  - (user_goals_met OR cycles > max_cycles)
```

## Subtree Selection (for weighted sampling)

```python
score = (
    c1 * (1 / visit_count)      # exploration
    + c2 * (1 - prop_coverage)  # incompleteness
    + c3 * centrality           # structural importance
)
```

## Cross-Cutting Concerns

When concepts span branches (e.g., "Digital" across Communication, Commerce):

1. **Default**: Single inheritance (tree)
2. **When needed**: Add properties (`isDigital: true`)
3. **If complex**: Multiple inheritance or faceted classification

## Bootstrapping

| Approach | Method |
|----------|--------|
| Top-down | User provides categories, system expands |
| Bottom-up | User provides instances, system clusters |
| Seed | Import reference ontology subset, customize |
| Intent-driven | LLM generates from user description |

## Key Design Decisions

| Decision | Recommendation |
|----------|----------------|
| Strategist view | Fixed summary + flags (start simple) |
| Output format | Structured output mode if available, else markdown + parser |
| Gap analysis | Direct LLM prompting (no KG infrastructure) |
| Termination | Convergence + coverage + user goals |
| Cross-cutting | Properties first, multiple inheritance only if needed |
