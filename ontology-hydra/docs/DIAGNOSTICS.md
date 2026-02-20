# Ontology Diagnostics Catalog

Reference catalog for the agent's diagnostic system. Organized by tier. Each check includes severity, implementation approach, whether it requires LLM evaluation, and a **hint** — guidance the agent can follow to investigate or fix the issue.

Hints range from short and obvious (Tier 1) to detailed natural language procedures (Tier 2-3). The exploration subagent reads the hint and follows it using its tools. This makes diagnostics extensible: adding a new check with a richer hint is equivalent to adding a new "skill" — no code changes needed beyond the detection logic.

Draws from: OOPS! pitfall catalog, OQuaRE, OntoClean, OntoMetrics.

## Execution Model

- **Always run (included in agent's prompt every outer turn):** All Tier 1 checks + deterministic triggers from Tier 2/3. Cheap, no LLM calls.
- **On-demand (agent dispatches exploration subagent):** Full Tier 2/3 analysis. The exploration subagent reads the hint and follows it using its tools. Costs an action.

A **trigger** is a cheap heuristic that flags a candidate without making a judgment. For example, D3.5's trigger is "class has no unique properties, one parent, no children" — this is deterministic, but whether the class *should* become a property requires judgment. The trigger surfaces the candidate; the agent decides whether to investigate.

Diagnostics marked with **[trigger]** below have a deterministic trigger that runs every outer turn. The full analysis (hint) runs on-demand.

## Severity Levels

| Level | Meaning | Agent behavior |
|---|---|---|
| **Critical** | Structurally invalid, logically broken | Must fix, cannot Finish |
| **Important** | Modeling issue, will likely cause problems | Should fix or explicitly suppress with reason |
| **Minor** | Style/quality issue or potential smell | Can suppress freely |

**Blocking diagnostics** are those that prevent `finish`: all Critical diagnostics and all Important diagnostics that are neither fixed nor investigated-and-suppressed. Minor diagnostics and unconfirmed triggers never block Finish.

---

## Tier 1: Deterministic

Pure graph/schema analysis. Zero ambiguity — either present or not.

### D1.1 Orphan Class
- **What:** Class with no parent (other than Thing), no children, not referenced in any property domain or range.
- **Severity:** Important
- **Detection:** Graph reachability. Build adjacency from `sub_class_of`, property `domain`, property `range`. Any class with degree 0 (excluding Thing) is orphaned.
- **Hint:** Connect this class to the hierarchy (add a parent or child), use it in a property domain/range, or delete it if it's not needed.
- **OOPS:** P04 (unconnected ontology elements)

### D1.2 Empty Property Domain
- **What:** Data or object property with empty `domain` list.
- **Severity:** Important
- **Detection:** `len(prop.domain) == 0`
- **Hint:** Assign domain classes to this property, or delete it if unused.
- **OOPS:** P11 (missing domain or range)

### D1.3 Empty Object Property Range
- **What:** Object property with empty `range` list.
- **Severity:** Important
- **Detection:** `len(prop.range) == 0`
- **Hint:** Assign range classes to this property, or delete it if unused.
- **OOPS:** P11

### D1.4 Dangling Class Reference
- **What:** A `ClassName` in `sub_class_of`, `domain`, `range`, or `IntersectionOf` that doesn't exist in `ontology.classes`.
- **Severity:** Critical
- **Detection:** Collect all referenced class names. Set-difference against `ontology.classes.keys()`.
- **Hint:** Either create the missing class or fix the reference to point to an existing class. Check for typos.
- **OOPS:** P04 variant

### D1.5 Hierarchy Cycle
- **What:** A class is transitively its own superclass via `sub_class_of` chains.
- **Severity:** Critical
- **Detection:** DFS cycle detection or `networkx.find_cycle()` on the `sub_class_of` digraph.
- **Hint:** Remove one of the sub_class_of edges in the cycle. Determine which direction the inheritance should actually go.
- **OOPS:** P06

### D1.6 Self-Referencing sub_class_of
- **What:** A class lists itself in its own `sub_class_of`.
- **Severity:** Critical
- **Detection:** `cls.name in cls.sub_class_of`
- **Hint:** Remove the self-reference. Determine the correct parent class.
- **OOPS:** P06 (degenerate case)

### D1.7 Property Name Collision
- **What:** A property name appears in both `data_properties` and `object_properties`.
- **Severity:** Important
- **Detection:** Set intersection of keys.
- **Hint:** Rename one of the properties to disambiguate, or determine if one should be deleted.

### D1.8 Empty Description
- **What:** A class or property has empty string `""` for `description.definition`.
- **Severity:** Minor
- **Detection:** String emptiness check.
- **Hint:** Add a meaningful definition that distinguishes this entity from its siblings and parent.
- **OOPS:** P08 (missing annotations)

### D1.9 Single-Element IntersectionOf
- **What:** `IntersectionOf` with only one class (semantically equivalent to just naming that class).
- **Severity:** Minor
- **Detection:** `len(intersection.classes) == 1`
- **Hint:** Replace with a direct class reference.

### D1.10 Naming Convention Violation
- **What:** Class names not PascalCase; property names not camelCase.
- **Severity:** Minor
- **Detection:** Regex. PascalCase: `^[A-Z][a-zA-Z0-9]*$`. camelCase: `^[a-z][a-zA-Z0-9]*$`.
- **Hint:** Rename to follow conventions. Classes: PascalCase. Properties: camelCase.

### D1.11 Flat Hierarchy
- **What:** Hierarchy is too shallow relative to class count. LLMs consistently produce flat hierarchies.
- **Severity:** Minor (depth = 1 with >5 classes → Important)
- **Detection:** Compute max hierarchy depth and class count. Flag if `max_depth < log₂(class_count) / 2` (e.g., 50 classes at depth 2 = flat). Degenerate case: depth = 1 with everything directly under Thing.
- **Hint:** Identify natural groupings among the top-level classes and introduce intermediate categories. Look for classes that share properties — they likely belong under a common parent.
- **Note:** This is a known LLM failure mode. LLMs tend to produce wide, shallow hierarchies rather than deep, well-structured ones.

### D1.12 Overly Broad Property Domain
- **What:** Property domain contains only root/high-level classes when more specific descendants exist.
- **Severity:** Minor
- **Detection:** Check if all domain classes are non-leaf and hierarchy depth > 2.
- **Hint:** Consider narrowing the domain to the most specific classes that actually use this property. Check if all descendants truly need it, or only a subset.

### D1.13 Singleton Property Domain
- **What:** Property whose domain contains exactly one class. May indicate over-specification — the property might belong on a parent class, or the class itself might not need to be separate.
- **Severity:** Minor
- **Detection:** `len(prop.domain) == 1` and the single domain class has a parent with subclasses that could plausibly share this property.
- **Hint:** Check if the property logically applies to the parent class or sibling classes. If other subclasses should also have this property, move the domain to the common parent. If it's truly specific to this one class, suppress.
- **Note:** LLMs tend to create properties with narrow domains because they process classes one at a time rather than considering the full hierarchy. This leads to redundant per-class properties that should be inherited.

### D1.14 Scattered Property Domain
- **What:** Property whose domain lists many unrelated classes (e.g., 5+ classes across different branches). Suggests the property should be on a common ancestor instead.
- **Severity:** Minor
- **Detection:** `len(prop.domain) >= 5` and the domain classes don't share a common ancestor within 2 levels (excluding Thing).
- **Hint:** Find the lowest common ancestor of the domain classes. If one exists at a reasonable level, move the property domain there. If the classes are truly unrelated, the property may be too generic — consider splitting it into more specific properties per branch.
- **Note:** Known LLM failure mode (OOPS P19 variant). LLMs tend to list every class that could use a property in the domain rather than placing it on a shared ancestor.

---

## Tier 2: Semantic

Potential modeling issues. Most detectable computationally, some benefit from LLM confirmation.

### D2.1 Near-Duplicate Class Names [trigger]
- **What:** Two class names with high string similarity (e.g., `Employee` vs `Employe`).
- **Severity:** Important
- **Detection:** Pairwise normalized Levenshtein or n-gram similarity. Threshold ~0.85.
- **Trigger:** String similarity above threshold.
- **LLM needed:** No for detection. Useful for confirmation.
- **Hint:** Examine both classes. If they represent the same concept, merge them (keep the better-named one, move properties). If distinct, rename to make the difference clearer.
- **OOPS:** P02 (synonyms as classes)

### D2.2 Near-Duplicate Property Names [trigger]
- **What:** Two property names with high string similarity (e.g., `hasLocation` vs `hasLocality`).
- **Severity:** Important
- **Detection:** Same as D2.1 on property names.
- **Trigger:** String similarity above threshold.
- **LLM needed:** No for detection.
- **Hint:** Compare the descriptions, domains, and ranges. If they serve the same purpose, merge. If distinct, rename to make the difference clear.
- **OOPS:** P13

### D2.3 Semantically Duplicate Classes [trigger]
- **What:** Different names but nearly identical descriptions.
- **Severity:** Important
- **Detection:** TF-IDF cosine similarity or token Jaccard on `description.definition`. Threshold ~0.7.
- **Trigger:** Description similarity above threshold.
- **LLM needed:** Partially. Bag-of-words catches obvious cases; LLM needed for paraphrases.
- **Hint:** Read both descriptions and their properties. Determine if they model the same real-world concept. If so, merge — pick the better name, union the properties, update all references. If they are genuinely distinct, rewrite descriptions to clearly differentiate them.

### D2.4 Semantically Duplicate Properties [trigger]
- **What:** Different names but overlapping descriptions and compatible domain/range.
- **Severity:** Important
- **Detection:** Combine name similarity + description similarity + domain/range overlap.
- **Trigger:** Combined similarity score above threshold.
- **LLM needed:** Partially.
- **Hint:** Compare descriptions, domains, and ranges side by side. If they express the same relationship, merge and update all references. If one is a specialization of the other, consider making it a sub-property (when supported) or clarifying the distinction.

### D2.5 Redundant Hierarchy Path
- **What:** Class C lists both B and A in `sub_class_of` where B is already a subclass of A. The direct link to A is redundant.
- **Severity:** Minor
- **Detection:** For each class, compute transitive closure of `sub_class_of`. If any direct parent is an ancestor of another direct parent, flag.
- **LLM needed:** No.
- **Hint:** Remove the redundant direct parent (the higher-level one). The inheritance is already implied through the chain.

### D2.6 God Class [trigger]
- **What:** A class appears in the domain of a disproportionate number of properties.
- **Severity:** Important
- **Detection:** Count domain references per class. Flag if > mean + 2*stddev or > 30% of all properties.
- **Trigger:** Property count exceeds threshold.
- **LLM needed:** No for detection. Useful for decomposition suggestions.
- **Hint:** Examine the properties on this class. Look for natural clusters — groups of properties that relate to a specific aspect or role. Consider splitting into subclasses or extracting a separate class for each cluster. For example, if a "Vehicle" has engine properties, maintenance properties, and registration properties, those might be three separate concerns.
- **OOPS:** P07 (merging different concepts)

### D2.7 Isolated Sub-Hierarchy
- **What:** A connected component in the hierarchy has no property bridges to the rest of the ontology.
- **Severity:** Important
- **Detection:** Build undirected graph with hierarchy edges + property domain/range connections. Find connected components.
- **LLM needed:** No.
- **Hint:** Determine if this sub-hierarchy is genuinely part of the domain. If yes, add object properties connecting it to the rest of the ontology. If not, consider removing it — it may have been added speculatively.

### D2.8 Unused Property
- **What:** Property whose domain classes have no subclasses and property is not referenced elsewhere.
- **Severity:** Minor
- **Detection:** Cross-reference property domains against hierarchy.
- **LLM needed:** No.
- **Hint:** Check if this property is needed. If the domain class is a leaf with no instances expected, the property may be over-specified. Consider deleting or broadening the domain.

### D2.9 Depth Imbalance [trigger]
- **What:** One branch significantly deeper than others.
- **Severity:** Minor
- **Detection:** Compute depth per leaf. Flag if `max_depth / avg_depth > 3`.
- **Trigger:** Depth ratio exceeds threshold.
- **LLM needed:** No.
- **Hint:** Examine the deep branch. Check if the intermediate classes each add meaningful distinctions (unique properties, different roles). If not, consider collapsing unnecessary intermediate levels. Check if the shallow branches are under-developed instead.

### D2.10 High Tangledness [trigger]
- **What:** Many classes with 2+ parents (excessive multiple inheritance).
- **Severity:** Minor
- **Detection:** `|classes with len(sub_class_of) > 1| / |total non-root classes|`. Flag above threshold.
- **Trigger:** Tangledness ratio exceeds threshold.
- **LLM needed:** No.
- **Hint:** For each multi-parent class, check if all parents are necessary. Sometimes one parent relationship is a "role" that should be modeled as a property instead of inheritance. Consider if IntersectionOf would be more appropriate.

### D2.11 Name-Description Mismatch
- **What:** Name suggests one thing, description says another.
- **Severity:** Important
- **Detection:** Weak heuristic (check if tokenized name appears in description). Unreliable.
- **LLM needed:** Yes for reliable detection.
- **Hint:** Either rename the entity to match its description, or rewrite the description to match the intended meaning of the name. Check the entity's usage (properties, hierarchy position) to determine which is correct.

### D2.12 Domain-Range Type Mismatch
- **What:** Object property where domain and range are the same class (reflexive) without justification, or domain and range in entirely unrelated branches.
- **Severity:** Minor
- **Detection:** Check if domain and range classes share ancestors beyond Thing.
- **LLM needed:** No for detection. LLM for judgment on legitimacy.
- **Hint:** For reflexive properties: verify the relationship genuinely connects instances of the same type (e.g., "adjacentTo" between Zones is valid). For cross-branch properties: verify the relationship is meaningful — if domain and range are in unrelated areas, the property might be too broad or misplaced.

---

## Tier 3: Heuristic

Patterns that *might* indicate problems but are frequently intentional. Highest false-positive rate.

### D3.1 Polysemous Name
- **What:** Class/property name that could refer to multiple distinct concepts (e.g., `Bank`, `Cell`).
- **Severity:** Minor
- **Detection:** WordNet synset count > 2 (limited coverage).
- **LLM needed:** Yes for reliable context-aware detection.
- **Hint:** Check if the name is ambiguous in the context of this ontology's domain. If it is, rename to the domain-specific meaning (e.g., `RiverBank` or `FinancialInstitution` instead of `Bank`). If the context makes the meaning obvious, suppress.
- **OOPS:** P01

### D3.2 Missing Inverse Property [trigger]
- **What:** Object property like `hasParent` without corresponding `isParentOf`/`hasChild`.
- **Severity:** Minor
- **Detection:** Name pattern matching (`has*`/`is*Of` pairs, `*By`/`*s` pairs).
- **Trigger:** Name matches inverse pattern but no matching counterpart exists.
- **LLM needed:** Partially. Patterns catch common cases.
- **Hint:** Determine if the inverse relationship is useful for the domain. If yes, create the inverse property with appropriate domain/range (swapped from the original). If the relationship is inherently one-directional, suppress.
- **OOPS:** P19
- **Note:** `inverse_of` field is planned but not yet implemented in the model. **This diagnostic cannot run until the field is added.** The trigger (name pattern matching) can still flag candidates, but the hint's "create the inverse property" action is not yet possible. Deferred to Phase 3.

### D3.3 Synonym Classes [trigger]
- **What:** Classes whose names are known synonyms but modeled as distinct (e.g., `Automobile` and `Car`).
- **Severity:** Important
- **Detection:** WordNet synonym lookup.
- **Trigger:** WordNet synsets overlap between two class names.
- **LLM needed:** Partially. WordNet for standard English; LLM for domain jargon.
- **Hint:** Compare descriptions, properties, and hierarchy positions. If they represent the same concept, merge — keep the more standard/domain-appropriate name, union properties, update all references. If they represent genuinely distinct concepts despite synonymous names, rename to disambiguate and clarify descriptions.
- **OOPS:** P02

### D3.4 Over-Specified Data Property Range [trigger]
- **What:** Data property uses `string` when a more specific type fits (e.g., `birthDate: string` → should be `date`).
- **Severity:** Minor
- **Detection:** Keyword heuristic: name contains "date" → expect date/datetime; "count"/"number"/"age" → int; "is"/"has" prefix → boolean; "price"/"amount"/"rate" → float.
- **Trigger:** Name-to-type heuristic disagrees with actual range.
- **LLM needed:** No for common patterns.
- **Hint:** Change the data property range to the more specific type suggested by its name and description. Check the description to confirm the intended semantics before changing.

### D3.5 Class That Should Be a Property [trigger]
- **What:** Class with exactly one property, one parent, no children, name suggests an attribute.
- **Severity:** Minor
- **Detection:** Structural filter (appears only in one property's range, has zero own properties).
- **Trigger:** Structural filter matches (no unique properties, single parent, no children, appears in exactly one property's range).
- **LLM needed:** Partially. Filter detects candidates; LLM judges.
- **Hint:** Examine if this class adds modeling value as a class (could it have instances? subclasses? multiple properties in the future?) or if it's simpler as a data property on the parent. If converting, add the data property to the parent class's domain and remove the class and its connecting object property.

### D3.6 Property That Should Be a Class [trigger]
- **What:** Data property whose value implies structured data (e.g., `address: string` when addresses have internal structure).
- **Severity:** Minor
- **Detection:** Flag string-typed properties matching structured-data patterns ("address", "location", "contact").
- **Trigger:** Name matches structured-data keyword list and range is string.
- **LLM needed:** Mostly yes.
- **Hint:** Determine if the property's value has internal structure that the ontology should represent. If yes, create a new class for it with appropriate data properties, then convert the original data property into an object property pointing to the new class. If the flat representation is sufficient for the domain, suppress.

### D3.7 OntoClean Violation
- **What:** Anti-rigid class (role/phase) subsumes rigid class (kind/type). E.g., `Student` as superclass of `Person`.
- **Severity:** Important
- **Detection:** Not feasible without LLM. Requires tagging each class with OntoClean metaproperties (rigid/anti-rigid/semi-rigid), then checking constraints.
- **LLM needed:** Yes.
- **Hint:** Classify each class in the flagged pair as rigid (essential identity — Person, Car), anti-rigid (contingent role — Student, Employee), or semi-rigid (default property — Tall, Heavy). If an anti-rigid class is a superclass of a rigid class, invert the relationship or restructure. Roles should be modeled as subclasses of their rigid kinds, not the reverse.
- **Reference:** [LLMs for OntoClean-based refinement](https://arxiv.org/html/2403.15864)

### D3.8 Abstraction Level Inconsistency [trigger]
- **What:** Sibling classes at different abstraction levels (e.g., under `Vehicle`: `Car`, `Truck`, `RedVehicle`).
- **Severity:** Minor
- **Detection:** Check if sibling names share lexical patterns; flag outliers.
- **Trigger:** Sibling name pattern outlier detected (e.g., one sibling name contains parent name while others don't).
- **LLM needed:** Yes for reliable detection.
- **Hint:** Examine the sibling classes. Identify which ones classify by the same criterion (e.g., function, structure, material) and which use a different criterion. Move outliers to a more appropriate location — either a different parent, a different branch, or model the distinguishing attribute as a property instead of a subclass.

### D3.9 Sparse Description
- **What:** Description is non-empty but minimal (e.g., "A sensor." for class `Sensor`).
- **Severity:** Minor
- **Detection:** Token count after stop-word removal. Flag if < 3 content words, or if description is just the class name with articles.
- **LLM needed:** No for basic detection.
- **Hint:** Rewrite the description to include: what the entity represents, how it differs from its siblings and parent, and what role it plays in the domain. A good description should let someone unfamiliar with the ontology understand why this entity exists.

### D3.10 Single-Child Chain [trigger]
- **What:** Chain A → B → C → D where each has exactly one child. Suggests over-classification or collapsible intermediates.
- **Severity:** Minor
- **Detection:** Walk hierarchy, flag chains of length > 2 where each node has exactly one child.
- **Trigger:** Chain of length > 2 detected.
- **LLM needed:** No.
- **Hint:** For each intermediate class in the chain, check if it adds a meaningful distinction (unique properties, different role, known real-world category). If not, collapse by removing the intermediate and connecting its parent directly to its child. If the chain represents a legitimate specialization path, suppress.

---

## Implementation Priority

**Phase 1 — Deterministic (zero false positives):**
D1.4, D1.5, D1.6, D1.1, D1.2, D1.3, D1.7, D1.8, D1.9, D1.10, D1.11, D1.12, D1.13, D1.14

**Phase 2 — Computational semantic (no LLM for detection):**
D2.1, D2.2, D2.5, D2.6, D2.7, D2.8, D2.9, D2.10, D2.12, D3.9, D3.10

**Phase 3 — LLM-assisted:**
D2.3, D2.4, D2.11, D3.1, D3.2, D3.3, D3.4, D3.5, D3.6, D3.7, D3.8

## Dependencies

- `networkx` (already available via symbolicai): cycles, components, depths, paths
- `difflib` (stdlib): basic string similarity
- `rapidfuzz` (optional): faster, more accurate string similarity

## Suppression Model

### Severity-Gated Suppression

Not all diagnostics are equally suppressible. The cost of suppression scales with severity to prevent the agent from taking the cheap path:

| Severity | Suppression rule |
|---|---|
| **Critical** | Never suppressible. Must be fixed. |
| **Important** | Suppressible only after investigation. Agent must dispatch an exploration subagent that confirms it's a false positive. The system rejects `suppress` actions for Important diagnostics that lack a preceding investigation report for that `(diagnostic_id, entity)` pair. |
| **Minor** | Freely suppressible with a reason. |

**Why:** Suppression is cheap (one bookkeeping action), fixing is expensive (explore + modify). Without gating, the agent has a perverse incentive to suppress rather than fix, especially since stopping requires zero unresolved blocking diagnostics. Severity-gating makes Important suppressions cost an action (the investigation), roughly equalizing the cost with starting to fix.

### Mechanics

- Each suppression is keyed to `(diagnostic_id, entity_name)`.
- Suppression includes a `reason` field (written by the agent or investigation subagent).
- Resurfaces if the entity's structural properties change (domain, range, sub_class_of, description).
- Auto-deleted if the entity is deleted from the ontology.

### Final Suppression Review

Before `finish` succeeds, the system injects all current suppressions into context and asks the agent to review them against the completed ontology. Diagnostics suppressed early in the run (when the ontology was small and the issue seemed irrelevant) may now be fixable. The agent must confirm or un-suppress each one. See DESIGN.md § Stopping Conditions.

## Sources

- [OOPS! Pitfall Catalogue](https://oops.linkeddata.es/catalogue.jsp)
- [Poveda-Villalon thesis](https://oa.upm.es/39448/1/MARIA_POVEDA_VILLALON.pdf)
- [OQuaRE framework](https://www.sciencedirect.com/science/article/abs/pii/S0957417412012146)
- [OntoClean (Wikipedia)](https://en.wikipedia.org/wiki/OntoClean)
- [LLMs for OntoClean refinement](https://arxiv.org/html/2403.15864)
- [OntoMetrics Graph Metrics](https://ontometrics.informatik.uni-rostock.de/wiki/index.php/Graph_Metrics)
- [OntoCheck (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3448530/)
