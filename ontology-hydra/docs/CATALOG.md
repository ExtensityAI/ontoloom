# Diagnostic Catalog

Complete catalog of ontology quality diagnostics. Each diagnostic has an ID, description, detection method, fix suggestion, and scope annotations indicating applicability to the current system.

For how diagnostics fit into the three-pass architecture, see [ARCHITECTURE.md](ARCHITECTURE.md) § Round Structure. For how deterministic findings feed into exploration, see [EXPLORATION.md](EXPLORATION.md) § Candidate Findings. For how findings become proposals, see [RESOLUTION.md](RESOLUTION.md).

---

## Scope Annotations

Each diagnostic is annotated with:

| Annotation | Meaning |
|---|---|
| **Applicable** | Runs against the current model (classes, properties, hierarchy) |
| **Deferred** | Requires model features not yet implemented (restrictions, equivalentClass, etc.) |
| **Deterministic** | Pure computation, no LLM calls. Runs in the deterministic pass. |
| **Exploration** | Requires LLM judgment. Runs in the exploration pass. |
| **Auto-fixable** | Mechanical fix, applied silently before exploration. |
| **[trigger]** | Has a cheap deterministic trigger that produces a **candidate finding** for the exploration pass to investigate. |

---

## Severity Levels

| Level | Meaning | Behavior |
|---|---|---|
| **Critical** | Structurally invalid, logically broken | Must fix. Cannot complete. |
| **Warning** | Modeling issue, will likely cause problems | Should fix or explicitly defer with reasoning. |
| **Info** | Style/quality issue, metric signal | Can defer freely. |

---

## 1. Structural & Graph Topology

### S01 — Disconnected Components / Orphan Classes `Critical` `Applicable` `Deterministic`
**What & Why:** Classes not connected to the rest of the ontology via any subClassOf, domain, range, or restriction edge. They float in isolation, unreachable by queries. OOPS! P04.
**Detection:** Run connected-component analysis on the class graph (subClassOf + objectProperty domain/range edges). Any class not reachable from the root is orphaned.
**Fix:** Connect to an appropriate superclass. If out of scope, remove.
**Tier:** 1

### S02 — Hierarchy Depth Imbalance `Warning` `Applicable` `Deterministic`
**What & Why:** Wildly uneven depth across branches — one branch 12 levels deep, a sibling only 2 — signals inconsistent modeling granularity. Very deep = over-classification; very shallow = under-modeling.
**Detection:** Compute max depth per root-to-leaf path. Flag if max_depth > 15 or depth variance > 2σ. Also flag max_depth ≤ 2 (lazy taxonomy).
**Fix:** Review deep branches for overspecialization. Review shallow branches for missing intermediate concepts.
**Tier:** 2

### S03 — Fan-Out Hotspots (Bus-Stop Anti-Pattern) `Warning` `Applicable` `Deterministic`
**What & Why:** A class with too many direct subclasses (e.g., 50+) — everything dumped under it without intermediate categories. Makes navigation, reasoning, and maintenance difficult.
**Detection:** Count direct subclasses per class. Flag any with >20. Compute branching factor; outliers >2σ above mean.
**Fix:** Introduce intermediate grouping classes. LLM can suggest natural groupings from child names.
**Tier:** 1 (top-level), 2 (deeper)

### S04 — Fan-In Anomalies (Excessive Multiple Inheritance) `Warning` `Applicable` `Deterministic`
**What & Why:** High tangledness (many classes with multiple parents) indicates error-prone manual polyhierarchy.
**Detection:** Tangledness = (classes with >1 parent) / total. Flag if >0.15. Flag individual classes with >3 parents.
**Fix:** Apply Rector normalization: single-inheritance primitive axis + defined classes.
**Tier:** 2

### S05 — Property Distribution Anomalies `Warning` `Applicable` `Deterministic`
**What & Why:** Classes with 0 properties ("empty shells") add no content. Classes with >15–20 properties ("God classes") conflate multiple concerns.
**Detection:** Per class, count properties where class is domain/range. Flag 0 and >2σ above mean.
**Fix:** Empty shells: add properties or demote. God classes: decompose.
**Tier:** 3 (expansion)

### S06 — Axiom-to-Class Ratio `Info` `Applicable` `Deterministic`
**What & Why:** Quick health indicator. Low ratio (<2) = pure taxonomy. High ratio (>20) = possible over-axiomatization.
**Detection:** Total logical axioms / total named classes.
**Fix:** If low: add restrictions, disjointness, equivalence axioms.
**Note:** With the current model (no axioms), this will always be low. The meta-diagnostic about "purely taxonomic" subsumes this.
**Tier:** N/A (info-only)

### S07 — Betweenness Centrality Bottlenecks `Warning` `Applicable` `Deterministic`
**What & Why:** A class with extremely high betweenness means most shortest paths pass through it. Fragility risk.
**Detection:** Compute betweenness centrality for all classes. Flag >3σ above mean.
**Fix:** Decompose the bottleneck class or add alternative paths.
**Tier:** 2

### S08 — Property Deserts (Taxonomic Islands) `Warning` `Applicable` `Deterministic`
**What & Why:** Subtrees with zero object properties — purely taxonomic islands that classify but don't relate.
**Detection:** Identify subtrees where no class is domain/range of any object property.
**Fix:** Add object properties connecting the island to other ontology regions.
**Tier:** 3 (expansion)

### S09 — Community-Concept Misalignment `Warning` `Applicable` `Deterministic`
**What & Why:** The ontology's detected graph communities don't match intended modules.
**Detection:** Louvain community detection; compare to intended modules. Low NMI = misalignment.
**Fix:** Refactor to align logical and intended structure.
**Tier:** 2

### S10 — Buried Important Concepts `Warning` `Applicable` `Deterministic`
**What & Why:** A structurally important class (high centrality) deeply nested (depth >5) is hard to discover.
**Detection:** Eigenvector centrality vs. hierarchy depth. Flag high-centrality + deep-nested.
**Fix:** Promote higher or create shortcut path.
**Tier:** 2

### S11 — Small-World Property Violation `Info` `Applicable` `Deterministic`
**What & Why:** Good ontologies have high local clustering with short global paths.
**Detection:** σ = (C/C_random) / (L/L_random). Well-structured ontologies: σ >> 1.
**Fix:** Improve local clustering; add hub classes for global connectivity.
**Tier:** N/A (info-only)

### S12 — Newman Modularity Score `Info` `Applicable` `Deterministic`
**What & Why:** Q < 0.3 = poor modularity. Q > 0.5 = good.
**Detection:** Compute Newman modularity Q.
**Fix:** Restructure to increase within-module cohesion.
**Tier:** N/A (info-only)

### S13 — Collapsible Linear Chain `Warning` `Applicable` `Deterministic`
**What & Why:** A class with exactly 1 parent and 1 child, no properties, no restrictions — a useless intermediate.
**Detection:** Find single-parent/single-child classes with no domain/range participation.
**Fix:** Collapse by connecting parent directly to child.
**Tier:** 2 (low priority within tier)

### S14 — Spectral Gap / Fiedler Value `Info` `Applicable` `Deterministic`
**What & Why:** Small second-smallest eigenvalue means near-disconnection. Fragile.
**Detection:** Compute λ₂ (Fiedler value). Near-zero = fragile.
**Fix:** Strengthen connections between weakly linked regions.
**Tier:** N/A (info-only)

### S15 — Coupling-Cohesion Metrics per Module `Warning` `Applicable` `Deterministic`
**What & Why:** Modules with high external references and low internal cohesion are poorly bounded.
**Detection:** Per module: NEC, NER, REC, NOP.
**Fix:** Refactor boundaries to minimize cross-module dependencies.
**Tier:** 2

---

## 2. Taxonomy Anti-Patterns

### T01 — Is-A Overloading: Instance-of as SubClassOf `Critical` `Applicable` `Exploration`
**What & Why:** "IBM subClassOf Company" says IBM is a *kind* of company. It should be an *instance*.
**Detection:** LLM judgment + NER on class names to detect proper nouns.
**Fix:** Convert child to individual with rdf:type.
**Hint:** Check if the child is a specific, named entity rather than a category. Proper nouns, brand names, and unique identifiers suggest instance, not class.
**Tier:** 2

### T02 — Is-A Overloading: Part-Whole as SubClassOf `Critical` `Applicable` `Exploration`
**What & Why:** "Engine subClassOf Car" says every engine is a car. The relationship is partOf.
**Detection:** LLM checks whether child is a component of parent.
**Fix:** Replace subClassOf with partOf/hasPart object property.
**Hint:** Ask: "Is every X a kind of Y?" If no, it's not is-a. Components, ingredients, and sections are parts, not subclasses.
**Tier:** 2

### T03 — Is-A Overloading: Constitution as SubClassOf `Critical` `Applicable` `Exploration`
**What & Why:** "WoodTable subClassOf Wood" — a table is not a kind of wood.
**Detection:** LLM checks if parent is material/substance and child is object.
**Fix:** Model using constitutedBy or hasMaterial property.
**Hint:** If the parent is a material or substance and the child is a physical object, the relationship is "made of," not "is a."
**Tier:** 2

### T04 — Is-A Overloading: Role as SubClassOf `Critical` `Applicable` `Exploration`
**What & Why:** "Student subClassOf Person" — Student is a role (anti-rigid), not a natural kind.
**Detection:** LLM + OntoClean rigidity assessment.
**Fix:** Model as separate class with hasRole/plays relationship.
**Hint:** Ask: "Can an instance stop being X without ceasing to exist?" If yes, X is a role, not a natural kind. Students can stop being students; persons can't stop being persons.
**Tier:** 2

### T05 — Overspecialization (Instances as Classes) `Warning` `Applicable` `Exploration`
**What & Why:** Leaf classes that should be individuals: "MeetingRoom3B" as a subclass.
**Detection:** LLM + heuristic: leaves with proper nouns, serial numbers.
**Fix:** Convert to individual.
**Tier:** 2

### T06 — Lazy/Flat Taxonomy `Warning` `Applicable` `Deterministic`
**What & Why:** Everything is a direct subclass of Thing. No intermediate grouping.
**Detection:** Flag if max_depth ≤ 2 or inheritance richness > 8 at top levels.
**Fix:** Introduce intermediate grouping classes.
**Tier:** 1

### T07 — Miscellaneous/Catch-All Classes `Warning` `Applicable` `Deterministic` `[trigger]`
**What & Why:** Classes like "OtherEntity" or "MiscellaneousItem" are wastebaskets.
**Detection:** Name patterns: Other*, Misc*, General*, Unclassified*. LLM for semantic catch-alls.
**Trigger:** Name pattern match.
**Fix:** Analyze intended members and create proper classes.
**Tier:** 2

### T08 — Missing Disjointness Between Siblings `Critical` `Deferred`
**What & Why:** Without disjointness, OWL allows an individual to be in multiple sibling classes.
**Detection:** For each sibling set, check for disjointWith or AllDisjointClasses.
**Note:** Deferred — disjointness axioms not in current model. The check can detect the *absence* deterministically but the fix requires axiom support.
**Tier:** 3

### T09 — Polysemous/Merged Concepts `Warning` `Applicable` `Exploration`
**What & Why:** A single class conflating multiple meanings (e.g., "Bank").
**Detection:** LLM + context: if the class's children span unrelated domains, likely polysemous.
**Fix:** Split into separate disambiguated classes.
**Tier:** 2

### T10 — Surface-Name Taxonomy `Warning` `Applicable` `Exploration`
**What & Why:** LLMs build taxonomies from string similarity. "GuitarCase subClassOf Guitar."
**Detection:** For subClassOf where child name contains parent as substring, LLM verifies.
**Fix:** Replace with correct relationship.
**Tier:** 2

### T11 — Temporal-Atemporal Conflation `Warning` `Applicable` `Exploration`
**What & Why:** Mixing temporally bounded roles with enduring kinds as siblings.
**Detection:** LLM + OntoClean rigidity check on siblings.
**Fix:** Separate role axis from kind axis.
**Tier:** 2

### T12 — Granularity Mismatch Across Subtrees `Warning` `Applicable` `Deterministic`
**What & Why:** 50 disease types but only 3 cancer types. Inconsistent granularity.
**Detection:** Compute depth and leaf count per top-level subtree. High coefficient of variation.
**Fix:** Harmonize granularity or document scope limitations.
**Tier:** 3 (expansion)

### T13 — Abstraction Level Mixing `Warning` `Applicable` `Exploration`
**What & Why:** "MathematicalObject" sibling to "Car" — incompatible abstraction levels.
**Detection:** LLM checks sibling pairs for wildly different abstraction levels.
**Fix:** Introduce intermediate abstract classes.
**Tier:** 2

### T14 — Umbrella Class Anti-Pattern `Warning` `Applicable` `Exploration`
**What & Why:** Parent whose children share no genuine common property. "Resource" containing Person, Document, Room.
**Detection:** LLM: for classes with >5 children, assess if all share a common essential property.
**Fix:** Split into specific superclasses.
**Tier:** 1

### T15 — Epistemic Intrusion `Warning` `Applicable` `Exploration`
**What & Why:** Classes encoding certainty rather than ontological categories: "SuspectedPregnancy."
**Detection:** LLM checks for epistemic status terms in class names.
**Fix:** Separate epistemic qualifiers into a distinct axis.
**Tier:** 2

### T16 — Category vs. Class Confusion `Warning` `Applicable` `Exploration`
**What & Why:** "ProductCategory" whose instances should be classes.
**Detection:** LLM + heuristic: names ending in Type, Category, Kind, Classification.
**Fix:** Use proper metaclass patterns.
**Tier:** 2

---

## 3. Property Modeling

### P01 — Multiple Domain/Range = Intersection Trap `Critical` `Applicable` `Deterministic`
**What & Why:** Multiple rdfs:domain are INTERSECTED, not unioned. Most developers expect union. OOPS! P19.
**Detection:** Find properties with >1 rdfs:domain or >1 rdfs:range.
**Fix:** Use owl:unionOf in a single domain/range declaration.
**Note:** The current model uses `list[ClassExpression]` for domain/range. The system should check whether the intent is intersection or union.
**Tier:** 3

### P02 — Domain/Range as Inference, Not Constraint `Critical` `Applicable` `Exploration`
**What & Why:** OWL domain/range are inference rules, not validation constraints.
**Detection:** LLM flags properties where domain/range reflects validation intent.
**Fix:** Ensure domain/range inferences are intended. Use SHACL for validation.
**Tier:** 3

### P03 — Missing Domain or Range `Warning` `Applicable` `Deterministic`
**What & Why:** Properties without domain/range provide no type information for reasoning. OOPS! P11.
**Detection:** Flag properties with no rdfs:domain and/or no rdfs:range.
**Fix:** Add appropriate declarations.
**Tier:** 3

### P04 — Domain/Range Set to owl:Thing `Warning` `Applicable` `Deterministic`
**What & Why:** Vacuous — equivalent to not declaring it at all.
**Detection:** Flag properties where domain or range is owl:Thing.
**Fix:** Set specific classes. If truly universal, omit rather than set owl:Thing.
**Note:** In the current model, this manifests as domain containing only the root class.
**Tier:** 3

### P05 — Over-Specialized Domain/Range `Warning` `Applicable` `Exploration`
**What & Why:** "hasName" restricted to a leaf class when it should apply broadly. OOPS! P18.
**Detection:** Flag properties whose domain/range is a leaf when name suggests broader applicability.
**Fix:** Broaden to the most general class that makes semantic sense.
**Tier:** 3

### P06 — Missing Inverse Properties `Warning` `Applicable` `Deterministic` `[trigger]`
**What & Why:** One-directional navigation limits query flexibility. OOPS! P13.
**Detection:** Name patterns: teaches/taughtBy, employs/employedBy, contains/containedIn.
**Trigger:** Name matches inverse pattern but no counterpart exists.
**Fix:** Add inverse property.
**Tier:** 3

### P07 — Self-Inverse Should Be Symmetric `Warning` `Deferred` `Auto-fixable`
**What & Why:** inverseOf(P, P) is correct but unnecessarily complex. OOPS! P25.
**Detection:** Find properties where owl:inverseOf points to itself.
**Fix:** Replace with symmetric declaration.
**Note:** Deferred — requires property characteristics support.

### P08 — Inverse Declared for Symmetric Property `Warning` `Deferred` `Auto-fixable`
**What & Why:** A symmetric property IS its own inverse; a separate inverse is redundant. OOPS! P26.
**Detection:** Properties declared both symmetric and having a distinct inverse.
**Fix:** Remove separate inverse.

### P09 — Wrong Transitive Declaration `Warning` `Deferred` `Exploration`
**What & Why:** "hasParent" transitive means grandparents become parents.
**Detection:** LLM reviews transitive declarations.
**Fix:** Remove transitivity from direct relationships.

### P10 — Missing Property Characteristics `Warning` `Deferred` `Exploration`
**What & Why:** Under-specified characteristics mean the reasoner can't make obvious inferences.
**Detection:** Name patterns: "unique" → functional; "sameAs" → symmetric; "partOf" → transitive.
**Fix:** Add appropriate characteristic declarations.

### P11 — Redundant Per-Class Properties `Warning` `Applicable` `Deterministic`
**What & Why:** personHasName, companyHasName, productHasName instead of one hasName.
**Detection:** String similarity >0.8 + shared range among properties differing only by class prefix.
**Fix:** Consolidate into single property.
**Tier:** 3

### P12 — Flat Property Hierarchy `Warning` `Applicable` `Deterministic`
**What & Why:** All properties at the same level with no sub-property structure.
**Detection:** Flag if >10 properties with max property hierarchy depth of 1.
**Fix:** Introduce sub-property relationships.
**Tier:** 3

### P13 — Inverse Pair Domain/Range Swap Check `Warning` `Applicable` `Deterministic`
**What & Why:** If P goes A→B, inverse Q must go B→A.
**Detection:** For all inverseOf pairs, verify domain(P) = range(Q) and vice versa.
**Fix:** Correct domain/range.
**Tier:** 3

### P14 — SubProperty Domain/Range Widening `Warning` `Applicable` `Deterministic`
**What & Why:** A sub-property with broader domain than its super is suspicious.
**Detection:** For each subPropertyOf, check domain(S) ⊆ domain(R) and range(S) ⊆ range(R).
**Fix:** Narrow the sub-property's domain/range.
**Tier:** 3

### P15 — Orphan Property (No Anchor) `Warning` `Applicable` `Deterministic`
**What & Why:** A property with no domain, no range, never referenced anywhere.
**Detection:** Scan for properties with zero connections.
**Fix:** Connect or remove.
**Tier:** 3

### P16 — Hallucinated Symmetry (LLM-Specific) `Warning` `Applicable` `Exploration`
**What & Why:** LLMs generate an inverse for every property, even meaningless ones.
**Detection:** LLM evaluates whether each inverse represents a genuinely useful relationship.
**Fix:** Remove vacuous inverses.
**Tier:** 3

### P17 — Copy-Paste Domain/Range (LLM-Specific) `Warning` `Applicable` `Deterministic`
**What & Why:** LLMs assign identical domain+range to clusters of properties by copying.
**Detection:** Find groups of 3+ properties sharing identical domain AND range.
**Fix:** Correct per property individually.
**Tier:** 3

### P18 — Parallel Property Consolidation Opportunity `Warning` `Applicable` `Exploration`
**What & Why:** teachesUndergrad, teachesGrad, teachesPhD — should be one "teaches."
**Detection:** Properties sharing name stem, same domain, different range (sibling classes).
**Fix:** Consolidate into single property.
**Tier:** 3

### P19 — Property Used Against Own Domain `Critical` `Deferred`
**What & Why:** Restriction on class disjoint from property's domain → unsatisfiable.
**Note:** Requires restriction support.

### P20 — SubProS Characteristic Compatibility `Warning` `Deferred`
**What & Why:** Property characteristics do NOT inherit as expected.
**Note:** Requires property characteristics support.

### P21 — Non-Simple Property in Forbidden Position `Critical` `Deferred`
**What & Why:** OWL 2 DL violation — non-simple property in cardinality/HasSelf/disjoint.
**Note:** Requires property chains and cardinality support.

### P22 — Equivalent Properties Not Declared `Warning` `Deferred`
**What & Why:** Duplicate properties without explicit equivalence.
**Note:** Requires equivalentProperty support.

---

## 4. Restriction & Axiom Anti-Patterns `Deferred`

All checks in this section (R01–R22) require restriction/axiom support not present in the current model. Listed here for completeness and future reference.

### R01 — Trivial Minimum Cardinality (minCard 0) `Warning` `Auto-fixable`
### R02 — Transitive Property + Cardinality `Critical`
### R03 — Vacuous Universal ("Only Without Some") `Warning`
### R04 — Existential with Intersection Unsatisfiability `Critical`
### R05 — Double Universal with Disjoint Fillers `Critical`
### R06 — Existential + Universal with Disjoint Fillers `Critical`
### R07 — No Unique Name Assumption Trap `Warning`
### R08 — Missing Functional Declaration `Warning`
### R09 — Complement Equivalence Trap `Warning`
### R10 — Inherited Restriction Conflict `Warning`
### R11 — Domain/Range vs. Restriction Mismatch `Warning`
### R12 — Restriction on Wrong Property Type `Warning`
### R13 — Contradictory Domain Through Restriction `Critical`
### R14 — Missing Closure Axioms `Warning`
### R15 — Flat Restriction Profile (LLM-Specific) `Warning`
### R16 — Existential/Universal Confusion `Critical`
### R17 — Necessary vs. Sufficient Confusion `Critical`
### R18 — Over-Specified Genus `Warning`
### R19 — Recursive Definition `Warning`
### R20 — GCI on owl:Thing `Warning`
### R21 — Hidden GCIs `Warning`
### R22 — Structural Tautologies `Warning` `Auto-fixable`

See the full DIAGS.md archive for detailed detection and fix descriptions for each.

---

## 5. Equivalence Class Traps `Deferred`

All checks (E01–E06) require equivalentClass support.

### E01 — Unintentional Entailed Equivalence `Critical`
### E02 — Equivalence to AllValuesFrom `Critical`
### E03 — Equivalence-Disjointness Contradiction `Critical`
### E04 — Equivalence Chains Across Imports `Warning`
### E05 — Cycle in SubClassOf Without Explicit Equivalence `Critical`

**Note:** E05 is partially applicable — cycle detection in subClassOf runs in the deterministic pass as a variant of hierarchy cycle detection.

### E06 — owl:equivalentClass as Property Misuse `Warning`

---

## 6. Naming & Labeling

### N01 — Inconsistent Casing Convention `Warning` `Applicable` `Deterministic` `Auto-fixable`
**What & Why:** Mixed casing looks unprofessional and causes tool errors. OOPS! P22.
**Detection:** Check all names against convention. Classes: PascalCase; properties: camelCase.
**Fix:** Standardize. Auto-fixable.
**Tier:** 4

### N02 — Plural Class Names `Warning` `Applicable` `Deterministic` `Auto-fixable`
**What & Why:** Classes represent concepts, not collections. "Animals" should be "Animal."
**Detection:** Flag names ending in "s" that appear plural (heuristic).
**Fix:** Rename to singular.
**Tier:** 4

### N03 — Instance-Like Class Names `Warning` `Applicable` `Deterministic` `[trigger]`
**What & Why:** Proper nouns, dates, serial numbers suggest these should be individuals.
**Detection:** NER + heuristic for proper nouns, dates, specific identifiers.
**Trigger:** NER pattern match.
**Fix:** Convert to individuals (requires exploration to confirm).
**Tier:** 2 (requires reclassification)

### N04 — Vague/Generic Names `Warning` `Applicable` `Deterministic`
**What & Why:** "Entity", "Object", "Data" provide no domain information.
**Detection:** Blocklist: Thing, Object, Entity, Concept, Item, Element, Resource, Misc, Other, General, Abstract, Base, Data, Info, Stuff.
**Fix:** Replace with domain-specific names.
**Tier:** 4

### N05 — Missing Labels/Annotations `Warning` `Applicable` `Deterministic`
**What & Why:** Entities without labels are incomprehensible. OOPS! P08.
**Detection:** Flag entities with no description.
**Fix:** Add descriptions.
**Tier:** 4

### N06 — Abbreviations Without Expansion `Warning` `Applicable` `Deterministic`
**What & Why:** Domain jargon incomprehensible to outsiders.
**Detection:** Flag sequences of 2+ capitals or short names <4 chars without expanding description.
**Fix:** Add full-name description.
**Tier:** 4

### N07 — Property Naming Convention Violations `Warning` `Applicable` `Deterministic` `[trigger]`
**What & Why:** Object properties should be verb phrases (hasX, isXOf); datatype properties noun phrases.
**Detection:** Pattern-match property names against conventions.
**Trigger:** Pattern mismatch.
**Fix:** Rename following conventions.
**Tier:** 4

### N08 — Duplicate Labels `Warning` `Applicable` `Deterministic`
**What & Why:** Distinct entities with same name cause ambiguity. OOPS! P32.
**Detection:** Group entities by name (class-property collision is N/A — separate namespaces).
**Fix:** Add disambiguating qualifiers.
**Note:** See also D1.7 for cross-namespace collisions (data property same name as object property).
**Tier:** 4

### N09 — Labels Containing Hierarchy Information `Warning` `Applicable` `Deterministic` `Auto-fixable`
**What & Why:** "Animal - Mammal - Dog" duplicates structural info.
**Detection:** Flag names with path separators or parent names.
**Fix:** Simplify.
**Tier:** 4

### N10 — Redundant Namespace in Local Name `Warning` `Applicable` `Deterministic`
**What & Why:** Namespace prefix repeated in local name.
**Detection:** Flag local names repeating the namespace/prefix.
**Fix:** Shorten.
**Tier:** 4

### N11 — Swapped Annotation Contents `Warning` `Applicable` `Deterministic` `Auto-fixable`
**What & Why:** Label longer than comment, or label contains sentences. OOPS! P20.
**Detection:** Flag if name is longer than description, or name contains periods.
**Fix:** Swap values.
**Note:** In the current model, this applies to `name` vs `description` fields.
**Tier:** 4

---

## 7. Redundancy & Duplication

### D01 — Redundant SubClassOf (Transitive Reduction) `Warning` `Applicable` `Deterministic` `Auto-fixable`
**What & Why:** A ⊑ B and B ⊑ C makes A ⊑ C redundant.
**Detection:** Compute transitive reduction. Any asserted edge already entailed is redundant.
**Fix:** Remove redundant edges.
**Tier:** 4

### D02 — Redundant EquivalentClass + SubClassOf `Warning` `Deferred` `Auto-fixable`
**What & Why:** EquivalentClasses(A,B) already implies both SubClassOf directions.
**Note:** Requires equivalentClass support.

### D03 — Semantically Equivalent Classes `Warning` `Applicable` `Deterministic` `[trigger]`
**What & Why:** Classes meaning the same thing but not declared equivalent.
**Detection:** Description similarity (TF-IDF cosine >0.7 or token Jaccard >0.7).
**Trigger:** Description similarity above threshold.
**Fix:** Merge or clarify distinction.
**Tier:** 2

### D04 — Semantically Equivalent Properties `Warning` `Applicable` `Deterministic` `[trigger]`
**What & Why:** Duplicate properties fragment data.
**Detection:** Name similarity + description similarity + domain/range overlap.
**Trigger:** Combined similarity above threshold.
**Fix:** Merge or clarify distinction.
**Tier:** 3

### D05 — Near-Duplicate Class Definitions `Warning` `Applicable` `Deterministic`
**What & Why:** Almost-identical property signatures suggest accidental duplication.
**Detection:** Jaccard similarity >0.8 over property signatures.
**Fix:** Merge or add distinguishing properties.
**Tier:** 2

### D06 — Duplicate Hierarchies `Warning` `Applicable` `Deterministic`
**What & Why:** Parallel isomorphic subtrees — maintenance nightmare.
**Detection:** Detect isomorphic subtrees.
**Fix:** Collapse into single hierarchy.
**Tier:** 2

### D07 — Synonyms as Separate Classes `Warning` `Deferred`
**What & Why:** "Car" and "Automobile" as distinct classes.
**Note:** Requires embedding similarity. The trigger-based approach using string similarity (D2.1/D2.3 below) provides partial coverage.

---

## 8. Modeling Pattern Violations

### M01 — God Class `Warning` `Applicable` `Deterministic` `[trigger]`
**What & Why:** Class with >15–20 associated properties — conflates multiple concerns.
**Detection:** Count properties per class. Flag >2σ above mean.
**Trigger:** Property count exceeds threshold.
**Fix:** Decompose into smaller classes.
**Tier:** 2

### M02 — Datatype-Only Class `Warning` `Applicable` `Deterministic`
**What & Why:** Class with only datatype properties and no object property connections.
**Detection:** Find classes with zero object property participation.
**Fix:** Connect via object properties or model as complex datatype.
**Tier:** 3

### M03 — Enumeration vs. Subclass Confusion `Warning` `Applicable` `Deterministic` `[trigger]`
**What & Why:** Small/Medium/Large as subclasses when enumeration is more appropriate.
**Detection:** Flag classes with 3–10 leaf subclasses all lacking unique properties.
**Trigger:** Structural pattern match.
**Fix:** Convert to enumeration or value partition pattern.
**Tier:** 2

### M04 — N-ary Relation Modeled as Binary `Warning` `Applicable` `Exploration`
**What & Why:** Binary properties can't capture multi-argument relationships.
**Detection:** LLM identifies co-occurring binary properties sharing contextual parameters.
**Fix:** Introduce reification class.
**Tier:** 3

### M05 — Missing Reification Opportunities `Warning` `Applicable` `Exploration`
**What & Why:** Properties needing temporal scope, provenance, or qualifiers.
**Detection:** LLM assesses each property for contextual information needs.
**Fix:** Apply reification pattern.
**Tier:** 3

### M06 — Lazy Primitive Ratio `Warning` `Deferred`
**What & Why:** 0% defined classes = pure taxonomy with no reasoning benefit.
**Note:** Requires equivalentClass support.

### M07 — Missing Part-Whole Patterns `Warning` `Applicable` `Exploration`
**What & Why:** Domains with natural components but no partOf/hasPart properties.
**Detection:** LLM + name patterns for composite domain concepts.
**Fix:** Add partOf/hasPart properties.
**Tier:** 3 (expansion)

### M08 — Duplicating Built-In Datatypes `Warning` `Applicable` `Deterministic`
**What & Why:** Classes like "StringValue" reinventing XSD datatypes. OOPS! P23.
**Detection:** Class names mirroring XSD type names.
**Fix:** Replace with datatype properties.
**Tier:** 2

### M09 — Using "is" Relation Instead of OWL Primitives `Critical` `Applicable` `Deterministic` `Auto-fixable`
**What & Why:** A manually created "is" or "isA" property instead of subClassOf. OOPS! P03.
**Detection:** Find properties named is, isA, is_a, type, instanceof.
**Fix:** Replace with OWL primitives.
**Tier:** 4

### M10 — Compound Names Without Matching Structure `Warning` `Applicable` `Exploration`
**What & Why:** "RedWine" without corresponding properties reflecting the "Red" modifier.
**Detection:** LLM flags compound names where modifier isn't reflected in properties.
**Fix:** Add properties matching name components.
**Note:** In the current model (no restrictions), this manifests as missing data/object properties rather than missing restrictions.
**Tier:** 3

---

## 9. OWL Semantics Traps `Deferred`

All checks (O01–O06) require full OWL expressivity.

### O01 — Open World Assumption Bias `Warning`
### O02 — OWL 2 DL Global Restriction Violations `Critical`
### O03 — Uncontrolled Punning `Warning`
### O04 — Profile-Breaking Construct Interaction `Warning`
### O05 — Expressivity Gap `Warning`
### O06 — SubClassOf ≠ ProperSubClassOf `Warning`

---

## 10. Property Chain Issues `Deferred`

All checks (PC01–PC05) require property chain support.

### PC01 — Chain Domain/Range Incompatibility `Critical`
### PC02 — Unintended Transitivity Inheritance `Warning`
### PC03 — Circular Property Chain `Critical`
### PC04 — Missing Useful Property Chains `Info`
### PC05 — Single-Element Property Chain `Warning` `Auto-fixable`

---

## 11. Datatype Property Issues

### DT01 — String-as-Enumeration `Warning` `Applicable` `Exploration`
**What & Why:** Free-text strings for fixed vocabularies.
**Detection:** String-typed properties with names suggesting closed sets.
**Fix:** Model as enumeration.
**Tier:** 3

### DT02 — String-as-Object-Property `Warning` `Applicable` `Exploration`
**What & Why:** Storing entity references as strings.
**Detection:** String-typed properties whose names suggest entity references.
**Fix:** Convert to object property.
**Tier:** 3

### DT03 — Boolean-as-Class `Warning` `Applicable` `Exploration`
**What & Why:** Two sibling subclasses representing true/false states.
**Detection:** LLM + heuristic: two sibling subclasses representing binary distinction.
**Fix:** Consider boolean datatype property.
**Tier:** 2

### DT04 — Language-Tagged vs. Plain String Confusion `Warning` `Deferred`
**Note:** Not applicable — current model doesn't distinguish language tags.

### DT05 — Unconstrained Numeric Ranges `Warning` `Applicable` `Exploration`
**What & Why:** "age" as integer allows negatives.
**Detection:** LLM flags numeric properties where domain implies constraints.
**Fix:** Use more specific datatype.
**Note:** Limited by current DataType enum.
**Tier:** 3

### DT06 — Date/Time Type Mixing `Warning` `Applicable` `Deterministic` `[trigger]`
**What & Why:** String-typed properties with date-like names.
**Detection:** Flag string-typed properties matching date patterns.
**Trigger:** Name pattern match + string range.
**Fix:** Use date/datetime type.
**Tier:** 4

---

## 12. Annotation & Documentation

### A01 — Inconsistent Language Tags `Warning` `Deferred`
**Note:** Not applicable — current model doesn't use language tags.

### A02 — Annotation Property Overloading `Warning` `Applicable` `Deterministic`
**What & Why:** Description field used for definitions, usage notes, and editorials simultaneously.
**Detection:** Flag descriptions exceeding threshold length or containing structured content.
**Fix:** Keep descriptions focused on definition.
**Tier:** 4

### A03 — Multiple Definitions `Warning` `Deferred`
**Note:** Current model has single description field per entity.

### A04 — Annotation Whitespace `Warning` `Applicable` `Deterministic` `Auto-fixable`
**What & Why:** Leading/trailing spaces, double spaces.
**Detection:** Regex for whitespace anomalies.
**Fix:** Trim.
**Tier:** 4

### A05 — Misleading Descriptions Contradicting Structure `Warning` `Applicable` `Exploration`
**Detection:** LLM compares description text with actual hierarchy/property structure.
**Fix:** Update description or structure.
**Tier:** 4

### A06 — Missing Provenance `Warning` `Deferred`
**Note:** Not applicable — current model doesn't track provenance annotations.

### A07 — Missing Ontology Declaration `Warning` `Deferred`
**Note:** Not applicable — current model doesn't include ontology-level metadata.

---

## 13. Import & Alignment `Deferred`

All checks (I01–I07) require import/namespace support not in current model.

---

## 14. Cross-Cutting Concern Entanglement

### CC01 — Temporal Baking `Warning` `Applicable` `Deterministic`
**What & Why:** FormerEmployee, CurrentStudent as classes instead of temporal properties.
**Detection:** Regex: Former*, Current*, Past*, Ex*, Previous*, Future*, Upcoming*.
**Fix:** Use temporal property with start/end dates.
**Tier:** 4

### CC02 — Spatial Baking `Warning` `Applicable` `Deterministic`
**What & Why:** NorthRegionStore as class instead of location property.
**Detection:** Regex: North*, South*, Downtown*, Remote*, Local*, Offshore*.
**Fix:** Model via hasLocation property.
**Tier:** 4

### CC03 — Status Baking `Warning` `Applicable` `Deterministic`
**What & Why:** ActiveSubscription, CancelledSubscription as subclasses.
**Detection:** Sibling classes sharing root with Active*, Inactive*, Pending*, Cancelled*, Expired*, Draft*.
**Fix:** Model as hasStatus → Status enumeration.
**Tier:** 4

### CC04 — Measure Baking `Warning` `Applicable` `Deterministic`
**What & Why:** weightInKilograms instead of measurement pattern.
**Detection:** Regex: *InKg, *InUSD, *InCelsius, *InMeters, *PerHour.
**Fix:** Use Measurement class with hasValue + hasUnit.
**Tier:** 4

---

## 15. Meta-Level & Level Mixing

### ML01 — Meta-Level Contamination `Warning` `Applicable` `Exploration`
**What & Why:** OntologyModule, ClassificationScheme as siblings of Person, Vehicle.
**Detection:** LLM flags meta-ontological names among domain classes.
**Fix:** Separate into distinct module or use annotations.
**Tier:** 1

### ML02 — Metaclass Confusion `Warning` `Applicable` `Exploration`
**What & Why:** Species with instances like Eagle, where Eagle is also a class.
**Detection:** LLM identifies ambiguous class/instance duality.
**Fix:** Use proper metaclass patterns with documentation.
**Tier:** 2

---

## 16. Intent Alignment

### IA01 — Domain Vocabulary Mismatch `Warning` `Applicable` `Exploration`
**What & Why:** Terms not belonging to the domain — "WeatherCondition" in a restaurant ontology.
**Detection:** LLM compares entities against domain context from scope document.
**Fix:** Remove out-of-domain entities.
**Tier:** 1

### IA02 — Scope Creep `Warning` `Applicable` `Exploration`
**What & Why:** Ontology contains concepts beyond requirements.
**Detection:** LLM compares content against scope document.
**Fix:** Remove unjustified entities.
**Tier:** 1

### IA03 — Superfluous Class Padding (LLM-Specific) `Warning` `Applicable` `Exploration`
**What & Why:** LLMs generate extra classes no requirement asks for.
**Detection:** Flag classes failing ALL: not in scope doc, not in any property domain/range, no properties.
**Fix:** Remove.
**Tier:** 1

### IA04 — Textbook Pattern Mismatch (LLM-Specific) `Warning` `Applicable` `Exploration`
**What & Why:** Every LLM ontology gets Agent→Person/Organization, Event→hasParticipant even when irrelevant.
**Detection:** LLM checks top-level classes against generic-pattern blocklist for domain relevance.
**Fix:** Remove unwarranted upper-level classes.
**Tier:** 1

---

## 17. Change History & Evolution `Deferred`

All checks (CH01–CH06) require change tracking infrastructure. The decision registry provides some of this capability, but formal change history tracking is deferred.

**Exception:** CH01 (orphaned references after deletion) is handled by the mutation API's cascade behavior — see [RESOLUTION.md](RESOLUTION.md) § Mutation API.

---

## 18. Reasoning Performance Anti-Patterns `Deferred`

All checks (RP01–RP05) require reasoning performance analysis. Not applicable without a reasoner.

---

## 19. Information-Theoretic & Evaluation Metrics

### IT01 — Intrinsic Information Content Imbalance `Info` `Applicable` `Deterministic`
**What & Why:** Skewed IC among siblings = hierarchy imbalance.
**Detection:** IC(c) = −log((hyponyms(c)+1) / max_nodes). Flag sibling groups with IC variance >2σ.
**Fix:** Balance by expanding under-differentiated branches.

### IT02 — Shannon Entropy of Hierarchy `Info` `Applicable` `Deterministic`
**What & Why:** Single number for overall balance.
**Detection:** Compute entropy over class probability distribution.
**Fix:** Target moderate entropy.

### IT03 — Relation Entropy `Info` `Applicable` `Deterministic`
**What & Why:** Low entropy = dominated by single relation type = semantically impoverished.
**Detection:** H = −Σ p(r) log p(r) for relation type distribution.
**Fix:** Add object properties for non-taxonomic relationships.

### IT04 — Relationship Richness (OntoQA) `Info` `Applicable` `Deterministic`
**What & Why:** RR = |P| / (|P| + |IsA|). RR ≈ 0 = pure taxonomy.
**Detection:** Compute ratio.
**Fix:** Increase RR by adding object properties.

### IT05 — Deductive Closure Gap `Info` `Deferred`
**Note:** Requires reasoner to compute inferred hierarchy.

### IT06 — OQuaRE Quality Score `Info` `Deferred`
**Note:** Subset of OQuaRE metrics computable without reasoner; full suite requires one.

---

## 20. Community-Specific Checks `Deferred`

Most checks (CS01–CS10) require full OWL expressivity or community-specific tooling.

**Exception:** CS06 (Distinctionary Pattern Violation — siblings differing only in name) is partially covered by D05 (near-duplicate class definitions) and M03 (enumeration vs subclass confusion).

---

## 21. Instance Population Readiness

### IP01 — Circular Instantiation Dependency `Warning` `Deferred`
**Note:** Requires restriction support.

### IP02 — Overly Strict Class `Warning` `Deferred`
**Note:** Requires restriction support.

### IP03 — Missing Identity Properties `Warning` `Applicable` `Exploration`
**What & Why:** Person, Product without any identifying property.
**Detection:** For non-abstract classes likely to have instances, check for functional data properties.
**Fix:** Add functional datatype property.
**Tier:** 3

---

## 22. Refactoring Opportunities `Deferred`

All checks (RF01–RF03) require restriction/axiom support for full implementation.

---

## Additional Diagnostics (from DIAGNOSTICS.md)

These diagnostics were identified during the design phase and are not in the original DIAGS.md catalog.

### D1.4 — Dangling Class Reference `Critical` `Applicable` `Deterministic`
**What:** A `ClassName` in `sub_class_of`, `domain`, `range`, or `IntersectionOf` that doesn't exist in `ontology.classes`.
**Detection:** Collect all referenced class names. Set-difference against `ontology.classes.keys()`.
**Hint:** Either create the missing class or fix the reference. Check for typos.
**Tier:** 1

### D1.7 — Property Name Collision `Important` `Applicable` `Deterministic`
**What:** A property name appears in both `data_properties` and `object_properties`.
**Detection:** Set intersection of keys.
**Hint:** Rename one of the properties to disambiguate.
**Tier:** 4

### D2.11 — Name-Description Mismatch `Important` `Applicable` `Exploration`
**What:** Name suggests one thing, description says another.
**Detection:** Weak heuristic (tokenized name in description). LLM for reliable detection.
**Hint:** Rename or rewrite description. Check usage to determine which is correct.
**Tier:** 4

### D3.4 — Over-Specified Data Property Range `Minor` `Applicable` `Deterministic` `[trigger]`
**What:** Data property uses `string` when a more specific type fits (e.g., `birthDate: string` → should be `date`).
**Detection:** Name-to-type heuristic ("date"→date, "count"→int, "is"/"has"→boolean, "price"→float).
**Trigger:** Heuristic disagrees with actual range.
**Hint:** Change range to more specific type suggested by name/description.
**Tier:** 4

### D3.5 — Class That Should Be a Property `Minor` `Applicable` `Deterministic` `[trigger]`
**What:** Class with no unique properties, single parent, no children.
**Detection:** Structural filter (zero own properties, single parent, no children, appears in exactly one property's range).
**Trigger:** Structural filter matches.
**Hint:** If class doesn't add modeling value (no instances, subclasses, or future properties), convert to data property on parent.
**Tier:** 2

### D3.6 — Property That Should Be a Class `Minor` `Applicable` `Deterministic` `[trigger]`
**What:** Data property whose value implies structured data ("address: string").
**Detection:** Flag string-typed properties matching structured-data patterns.
**Trigger:** Name matches keyword list + range is string.
**Hint:** If value has internal structure, create a new class with data properties and convert to object property.
**Tier:** 3

### D3.9 — Sparse Description `Minor` `Applicable` `Deterministic`
**What:** Description is non-empty but minimal (e.g., "A sensor." for class Sensor).
**Detection:** Token count after stop-word removal. Flag if <3 content words or description is just the name with articles.
**Hint:** Rewrite to include: what the entity represents, how it differs from siblings/parent, what role it plays.
**Tier:** 4

---

## Auto-Fixable Diagnostics (Summary)

Applied silently in the auto-fix pass before exploration:

| ID | Fix |
|---|---|
| N01 | Re-case to convention |
| N02 | Singularize plural names |
| N09 | Simplify path-containing labels |
| N11 | Swap name/description when name is longer |
| A04 | Trim whitespace |
| D01 | Remove redundant subClassOf (transitive reduction) |
| M09 | Replace "is"/"isA" property with OWL primitive |

---

## Pass Assignment Summary

### Deterministic Pass (no LLM)

**Structural:** S01–S15
**Taxonomy (structural subset):** T06, T07 (name patterns), T12 (coefficient of variation)
**Property:** P01, P03, P04, P06 (trigger), P11, P12, P13, P14, P15, P17
**Naming:** N01–N11
**Redundancy:** D01, D03 (trigger), D04 (trigger), D05, D06
**Metrics:** IT01–IT04
**Cross-cutting:** CC01–CC04
**Modeling:** M01 (trigger), M02, M03 (trigger), M08, M09
**Instance readiness:** IP01
**Additional:** D1.4, D1.7, D3.4 (trigger), D3.5 (trigger), D3.6 (trigger), D3.9

### Exploration Pass (LLM judgment)

**Taxonomy:** T01–T05, T09–T11, T13–T16
**Property:** P02, P05, P16, P18
**Modeling:** M04, M05, M07, M10
**Intent alignment:** IA01–IA04
**Meta-level:** ML01, ML02
**Datatype:** DT01, DT02, DT03, DT05
**Annotation:** A05
**Instance readiness:** IP03
**Additional:** D2.11
**Coverage gaps** (not in catalog — emergent from exploration)

---

## Sources

- [OOPS! Pitfall Catalogue](https://oops.linkeddata.es/catalogue.jsp) — Poveda-Villalón 2016
- [OQuaRE framework](https://www.sciencedirect.com/science/article/abs/pii/S0957417412012146)
- [OntoClean (Wikipedia)](https://en.wikipedia.org/wiki/OntoClean)
- [LLMs for OntoClean refinement](https://arxiv.org/html/2403.15864) — Zhao et al. 2024
- [OntoMetrics Graph Metrics](https://ontometrics.informatik.uni-rostock.de/wiki/index.php/Graph_Metrics)
- [OntoCheck (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3448530/)
- Rector et al. "OWL Pizzas" (EKAW 2004)
- Keet SubProS/ProChainS (EKAW 2012)
- Pellint — Lin & Sirin (OWLED 2008)
- Roussey & Corcho anti-pattern catalog (K-CAP 2009)
- Sales & Guizzardi OntoUML (DKE 2015)
- Lopez-Garcia & Schulz SNOMED (PLOS ONE 2016)
- Ontogenia/ESWC 2025
