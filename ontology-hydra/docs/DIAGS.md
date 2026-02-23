# Ontology Quality Diagnostics Catalog

> **Scope:** OWL subset — `owl:Class`, `rdfs:subClassOf`, `owl:ObjectProperty`, `owl:DatatypeProperty`, `rdfs:subPropertyOf`, `rdfs:domain`, `rdfs:range`, `owl:intersectionOf`, `owl:inverseOf`, `owl:equivalentClass`
>
> **Format:** Each diagnostic has an ID, description (what & why), detection method, and fix suggestion.
>
> **Severity:** Critical | Warning | Info
>
> **Detection types:** Deterministic, Embedding-based, LLM judgment, Graph-theoretic, Hybrid

---

## 1. Structural & Graph Topology

### S01 — Disconnected Components / Orphan Classes `Critical`
**What & Why:** Classes not connected to the rest of the ontology via any subClassOf, domain, range, or restriction edge. They float in isolation, unreachable by queries. OOPS! P04.
**Detection:** Run connected-component analysis on the class graph (subClassOf + objectProperty domain/range edges). Any class not reachable from the root is orphaned.
**Fix:** Connect to an appropriate superclass. If out of scope, remove.

### S02 — Hierarchy Depth Imbalance `Warning`
**What & Why:** Wildly uneven depth across branches — one branch 12 levels deep, a sibling only 2 — signals inconsistent modeling granularity. Very deep = over-classification; very shallow = under-modeling.
**Detection:** Compute max depth per root-to-leaf path. Flag if max_depth > 15 or depth variance > 2σ. Also flag max_depth ≤ 2 (lazy taxonomy).
**Fix:** Review deep branches for overspecialization. Review shallow branches for missing intermediate concepts.

### S03 — Fan-Out Hotspots (Bus-Stop Anti-Pattern) `Warning`
**What & Why:** A class with too many direct subclasses (e.g., 50+) — everything dumped under it without intermediate categories. Makes navigation, reasoning, and maintenance difficult.
**Detection:** Count direct subclasses per class. Flag any with >20. Compute branching factor; outliers >2σ above mean.
**Fix:** Introduce intermediate grouping classes. LLM can suggest natural groupings from child names.

### S04 — Fan-In Anomalies (Excessive Multiple Inheritance) `Warning`
**What & Why:** High tangledness (many classes with multiple parents) indicates error-prone manual polyhierarchy. Ontologies should use defined classes and let the reasoner infer polyhierarchy.
**Detection:** Tangledness = (classes with >1 parent) / total. Flag if >0.15. Flag individual classes with >3 parents.
**Fix:** Apply Rector normalization: single-inheritance primitive axis + defined classes that create polyhierarchy through reasoning.

### S05 — Property Distribution Anomalies `Warning`
**What & Why:** Classes with 0 properties ("empty shells") add no content. Classes with >15–20 properties ("God classes") conflate multiple concerns.
**Detection:** Per class, count properties where class is domain/range or appears in restrictions. Flag 0 and >2σ above mean.
**Fix:** Empty shells: add properties or demote. God classes: decompose into smaller focused classes.

### S06 — Axiom-to-Class Ratio `Info`
**What & Why:** Quick health indicator. Low ratio (<2) = pure taxonomy with no logical content. High ratio (>20) = possible over-axiomatization.
**Detection:** Total logical axioms / total named classes.
**Fix:** If low: add restrictions, disjointness, equivalence axioms. If high: check for redundancy.

### S07 — Betweenness Centrality Bottlenecks `Warning`
**What & Why:** A class with extremely high betweenness means most shortest paths pass through it. Removing it would disconnect the ontology. Fragility and maintenance risk. (Hoser et al. ESWC 2006)
**Detection:** Compute betweenness centrality for all classes. Flag >3σ above mean.
**Fix:** Decompose the bottleneck class or add alternative paths.

### S08 — Property Deserts (Taxonomic Islands) `Warning`
**What & Why:** Subtrees with zero object properties — purely taxonomic islands that classify but don't relate. Queries requiring cross-domain traversal will fail.
**Detection:** Identify subtrees where no class is domain/range of any object property and none has restrictions.
**Fix:** Add object properties connecting the island to other ontology regions.

### S09 — Community-Concept Misalignment `Warning`
**What & Why:** The ontology's detected graph communities don't match intended modules. Concepts meant to be separate are tightly coupled.
**Detection:** Louvain community detection; compare to intended modules (from name prefixes or annotations). Low NMI = misalignment.
**Fix:** Refactor to align logical and intended structure.

### S10 — Buried Important Concepts `Warning`
**What & Why:** A structurally important class (high centrality) that is deeply nested (depth >5) is hard to discover.
**Detection:** Eigenvector centrality or PageRank vs. hierarchy depth. Flag high-centrality + deep-nested.
**Fix:** Promote higher or create shortcut path.

### S11 — Small-World Property Violation `Info`
**What & Why:** Good ontologies have high local clustering with short global paths. Violation suggests poor organization.
**Detection:** σ = (C/C_random) / (L/L_random). Well-structured ontologies: σ >> 1.
**Fix:** Improve local clustering within groups; add hub classes for global connectivity.

### S12 — Newman Modularity Score `Info`
**What & Why:** Q < 0.3 = poor modularity (monolithic tangle). Q > 0.5 = good. Compute on both asserted AND inferred graphs — gap is diagnostic signal (Vrandečić & Sure).
**Detection:** Compute Newman modularity Q.
**Fix:** Restructure to increase within-module cohesion.

### S13 — Collapsible Linear Chain `Warning`
**What & Why:** A class with exactly 1 parent and 1 child, no properties, no restrictions, no equivalentClass — a useless intermediate.
**Detection:** Find single-parent/single-child classes with no domain/range participation, no restrictions, no equivalentClass.
**Fix:** Collapse by connecting parent directly to child. Auto-fixable.

### S14 — Spectral Gap / Fiedler Value `Info`
**What & Why:** Small second-smallest eigenvalue of graph Laplacian means near-disconnection. One edge removal could split the ontology.
**Detection:** Compute λ₂ (Fiedler value). Near-zero = fragile.
**Fix:** Strengthen connections between weakly linked regions. Fiedler vector identifies the near-split.

### S15 — Coupling-Cohesion Metrics per Module `Warning`
**What & Why:** Modules with high external references and low internal cohesion are poorly bounded. Affects reusability and maintainability.
**Detection:** Per module: NEC (external classes), NER (external relations), REC (ratio external), NOP (cross-boundary properties).
**Fix:** Refactor boundaries to minimize cross-module dependencies.

---

## 2. Taxonomy Anti-Patterns

### T01 — Is-A Overloading: Instance-of as SubClassOf `Critical`
**What & Why:** "IBM subClassOf Company" says IBM is a *kind* of company. It should be an *instance* of Company. The most common taxonomy error.
**Detection:** LLM judgment + NER on class names to detect proper nouns.
**Fix:** Convert child to owl:NamedIndividual with rdf:type.

### T02 — Is-A Overloading: Part-Whole as SubClassOf `Critical`
**What & Why:** "Engine subClassOf Car" says every engine is a car. The relationship is partOf, not is-a.
**Detection:** LLM checks whether child is a component of parent.
**Fix:** Replace subClassOf with partOf/hasPart object property restriction.

### T03 — Is-A Overloading: Constitution as SubClassOf `Critical`
**What & Why:** "WoodTable subClassOf Wood" — a table is not a kind of wood, it is made of wood.
**Detection:** LLM checks if parent is material/substance and child is object made of it.
**Fix:** Model using constitutedBy or hasMaterial property.

### T04 — Is-A Overloading: Role as SubClassOf `Critical`
**What & Why:** "Student subClassOf Person" — Student is a role (anti-rigid per OntoClean), not a natural kind. Instances can stop being students. (Zhao et al. 2024 show LLMs can serve as OntoClean taggers.)
**Detection:** LLM + OntoClean rigidity assessment.
**Fix:** Model as separate class with hasRole/plays relationship, or use Description-and-Situation pattern.

### T05 — Overspecialization (Instances as Classes) `Warning`
**What & Why:** Leaf classes that should be individuals: "MeetingRoom3B" as a subclass instead of instance. OOPS! P17.
**Detection:** LLM + heuristic: leaves with proper nouns, serial numbers, no restrictions.
**Fix:** Convert to owl:NamedIndividual.

### T06 — Lazy/Flat Taxonomy `Warning`
**What & Why:** Everything is a direct subclass of owl:Thing. No intermediate grouping. Provides no classification benefit.
**Detection:** Flag if max_depth ≤ 2 or inheritance richness > 8 at top levels.
**Fix:** Introduce intermediate grouping classes.

### T07 — Miscellaneous/Catch-All Classes `Warning`
**What & Why:** Classes like "OtherEntity" or "MiscellaneousItem" are wastebaskets that undermine classification. OOPS! P21.
**Detection:** Name patterns: Other*, Misc*, General*, Unclassified*. LLM for semantic catch-alls.
**Fix:** Analyze intended members and create proper classes.

### T08 — Missing Disjointness Between Siblings `Critical`
**What & Why:** Without disjointness, OWL's open world allows an individual to be in multiple sibling classes. The #1 source of reasoning confusion. OOPS! P10.
**Detection:** For each sibling set (sharing a parent), check for owl:disjointWith or AllDisjointClasses.
**Fix:** Add AllDisjointClasses axioms. Verify with LLM whether any siblings genuinely overlap.

### T09 — Polysemous/Merged Concepts `Warning`
**What & Why:** A single class conflating multiple meanings (e.g., "Bank" for financial institution and river bank). OOPS! P01, P07.
**Detection:** LLM + embeddings: if nearest neighbors span unrelated domains, likely polysemous.
**Fix:** Split into separate disambiguated classes.

### T10 — Surface-Name Taxonomy `Warning`
**What & Why:** LLMs build taxonomies from string similarity. "GuitarCase subClassOf Guitar" — a case is not a guitar.
**Detection:** For subClassOf where child name contains parent as substring, LLM verifies whether genuinely taxonomic.
**Fix:** Replace with correct relationship (partOf, usedWith, etc.).

### T11 — Temporal-Atemporal Conflation `Warning`
**What & Why:** Mixing temporally bounded roles with enduring kinds as siblings. Student (anti-rigid) as sibling of Person (rigid) violates OntoClean.
**Detection:** LLM + OntoClean rigidity check on siblings.
**Fix:** Separate role axis from kind axis.

### T12 — Granularity Mismatch Across Subtrees `Warning`
**What & Why:** 50 heart disease types but only 3 cancer types. Inconsistent granularity signals incomplete modeling.
**Detection:** Compute depth and leaf count per top-level subtree. High coefficient of variation = mismatch.
**Fix:** Harmonize granularity or document scope limitations.

### T13 — Abstraction Level Mixing `Warning`
**What & Why:** "MathematicalObject" sibling to "Car" — incompatible abstraction levels as siblings.
**Detection:** LLM checks sibling pairs for wildly different abstraction levels.
**Fix:** Introduce intermediate abstract classes.

### T14 — Umbrella Class Anti-Pattern `Warning`
**What & Why:** Parent whose children share no genuine common property. "Resource" containing Person, Document, Room.
**Detection:** LLM: for classes with >5 children, assess if all share a common essential property.
**Fix:** Split into specific superclasses.

### T15 — Epistemic Intrusion `Warning`
**What & Why:** Classes encoding certainty rather than ontological categories: "SuspectedPregnancy" mixed with "EctopicPregnancy." Mixes knowledge with knowledge-about-knowledge.
**Detection:** LLM checks for epistemic status terms in class names.
**Fix:** Separate epistemic qualifiers into a distinct axis linked by properties.

### T16 — Category vs. Class Confusion `Warning`
**What & Why:** "ProductCategory" whose instances (Electronics, Clothing) should be classes. Conflates classification schemes with classified things.
**Detection:** LLM + heuristic: names ending in Type, Category, Kind, Classification.
**Fix:** Use proper metaclass patterns or SKOS ConceptScheme.

---

## 3. Property Modeling

### P01 — Multiple Domain/Range = Intersection Trap `Critical`
**What & Why:** Multiple rdfs:domain declarations are INTERSECTED, not unioned. Most developers expect union. The most common critical pitfall in LLM-generated ontologies. OOPS! P19. (Ontogenia 2025)
**Detection:** Find properties with >1 rdfs:domain or >1 rdfs:range.
**Fix:** Use owl:unionOf in a single domain/range declaration. Auto-fixable if intent is union.

### P02 — Domain/Range as Inference, Not Constraint `Critical`
**What & Why:** OWL domain/range are inference rules, not validation constraints. If P has domain A and you assert x P y, OWL *infers* x is an A — it does NOT reject the assertion. The #1 OWL trap for database-background users.
**Detection:** LLM flags properties where domain/range likely reflects validation intent.
**Fix:** Use SHACL for validation. Ensure domain/range inferences are intended.

### P03 — Missing Domain or Range `Warning`
**What & Why:** Properties without domain/range provide no type information for reasoning. OOPS! P11.
**Detection:** Flag properties with no rdfs:domain and/or no rdfs:range.
**Fix:** Add appropriate declarations. LLM infers from name and context.

### P04 — Domain/Range Set to owl:Thing `Warning`
**What & Why:** Vacuous — equivalent to not declaring it at all.
**Detection:** Flag properties where domain or range is owl:Thing.
**Fix:** Set specific classes. If truly universal, omit rather than set owl:Thing.

### P05 — Over-Specialized Domain/Range `Warning`
**What & Why:** "hasName" restricted to a leaf class when it should apply broadly. Forces redundant parallel properties. OOPS! P18.
**Detection:** Flag properties whose domain/range is a leaf when name suggests broader applicability.
**Fix:** Broaden to the most general class that makes semantic sense.

### P06 — Missing Inverse Properties `Warning`
**What & Why:** One-directional navigation limits query flexibility. OOPS! P13.
**Detection:** Name patterns: teaches/taughtBy, employs/employedBy, contains/containedIn.
**Fix:** Add owl:inverseOf where bidirectional navigation is useful.

### P07 — Self-Inverse Should Be Symmetric `Warning`
**What & Why:** inverseOf(P, P) is correct but unnecessarily complex. OOPS! P25.
**Detection:** Find properties where owl:inverseOf points to itself.
**Fix:** Replace with owl:SymmetricProperty. Auto-fixable.

### P08 — Inverse Declared for Symmetric Property `Warning`
**What & Why:** A symmetric property IS its own inverse; a separate inverse is redundant. OOPS! P26.
**Detection:** Properties declared both symmetric and having a distinct inverse.
**Fix:** Remove separate inverse. Auto-fixable.

### P09 — Wrong Transitive Declaration `Warning`
**What & Why:** "hasParent" transitive means grandparents become parents. Wrong for "direct" relationships. OOPS! P28, P29.
**Detection:** LLM reviews transitive declarations.
**Fix:** Remove transitivity from direct relationships. Use separate transitive/non-transitive properties.

### P10 — Missing Property Characteristics `Warning`
**What & Why:** Under-specified characteristics mean the reasoner can't make obvious inferences.
**Detection:** Name patterns: "unique"/"primary" → functional; "sameAs"/"near" → symmetric; "partOf" → transitive.
**Fix:** Add appropriate characteristic declarations.

### P11 — Redundant Per-Class Properties `Warning`
**What & Why:** personHasName, companyHasName, productHasName instead of one hasName property.
**Detection:** Embedding similarity >0.8 + shared range among properties differing only by class prefix.
**Fix:** Consolidate into single property with appropriate domain. Auto-fixable.

### P12 — Flat Property Hierarchy `Warning`
**What & Why:** All properties directly under owl:topObjectProperty with no sub-property structure. Misses reasoning opportunities.
**Detection:** Flag if >10 properties with max property hierarchy depth of 1.
**Fix:** Introduce sub-property relationships where natural generalizations exist.

### P13 — Inverse Pair Domain/Range Swap Check `Warning`
**What & Why:** If P goes A→B, inverse Q must go B→A. Explicit domain/range contradicting this creates silent errors.
**Detection:** For all inverseOf(P,Q), verify domain(P) = range(Q) and vice versa.
**Fix:** Correct domain/range. Auto-fixable.

### P14 — SubProperty Domain/Range Widening `Warning`
**What & Why:** A sub-property with broader domain than its super is suspicious — sub-properties should specialize.
**Detection:** For each S subPropertyOf R, check domain(S) ⊆ domain(R) and range(S) ⊆ range(R).
**Fix:** Narrow the sub-property's domain/range or reconsider the hierarchy.

### P15 — Orphan Property (No Anchor) `Warning`
**What & Why:** A property with no domain, no range, never in any restriction, not sub/super of anything. Completely floating.
**Detection:** Scan for properties with zero connections.
**Fix:** Connect or remove.

### P16 — Hallucinated Symmetry (LLM-Specific) `Warning`
**What & Why:** LLMs generate an inverse for every property, even meaningless ones like "isBirthDatedBy."
**Detection:** LLM evaluates whether each inverse represents a genuinely useful relationship.
**Fix:** Remove vacuous inverses.

### P17 — Copy-Paste Domain/Range (LLM-Specific) `Warning`
**What & Why:** LLMs assign identical domain+range to clusters of properties by copying from the first generated.
**Detection:** Find groups of 3+ properties sharing identical domain AND range. LLM confirms different ranges warranted.
**Fix:** Correct per property individually.

### P18 — Parallel Property Consolidation Opportunity `Warning`
**What & Why:** teachesUndergrad, teachesGrad, teachesPhD — should be one "teaches" with range restrictions.
**Detection:** Properties sharing a name stem, same domain, different range (by sibling classes).
**Fix:** Consolidate into single property with range restrictions.

### P19 — Property Used Against Own Domain `Critical`
**What & Why:** Restriction ∃P.X on class C disjoint from P's domain → C becomes unsatisfiable via domain inference.
**Detection:** For each restriction, verify the class is compatible with the property's domain.
**Fix:** Broaden domain, adjust class hierarchy, or use different property.

### P20 — SubProS Characteristic Compatibility `Warning`
**What & Why:** Property characteristics do NOT inherit as expected — only functionality inherits. Transitivity, symmetry, inverse do NOT propagate down. Developers routinely assume otherwise. (Keet, EKAW 2012)
**Detection:** For each S subPropertyOf R, verify compatibility: R asymmetric → S can't be symmetric; transitivity conflicts with asymmetry/irreflexivity.
**Fix:** Explicitly declare characteristics on sub-properties.

### P21 — Non-Simple Property in Forbidden Position `Critical`
**What & Why:** A property in a chain (non-simple) cannot be in cardinality, HasSelf, disjoint, irreflexive, or asymmetric. OWL 2 DL violation.
**Detection:** Check all cardinality/HasSelf/disjoint/irreflexive/asymmetric axioms for non-simple properties.
**Fix:** Use a simple property or remove the chain.

### P22 — Equivalent Properties Not Declared `Warning`
**What & Why:** Duplicate properties without explicit equivalence cause fragmented data. OOPS! P12.
**Detection:** Embedding similarity >0.9 + same domain/range.
**Fix:** Merge or declare owl:equivalentProperty.

---

## 4. Restriction & Axiom Anti-Patterns

### R01 — Trivial Minimum Cardinality (minCard 0) `Warning`
**What & Why:** minCardinality 0 is a tautology — everything has ≥0 of anything. Adds no information.
**Detection:** Find all minCardinality 0 / minQualifiedCardinality 0.
**Fix:** Remove entirely. Auto-fixable.

### R02 — Transitive Property + Cardinality `Critical`
**What & Why:** OWL 2 DL forbids cardinality on transitive (or chain-involved) properties. ELK silently ignores; Pellet rejects. Creates reasoner-dependent behavior.
**Detection:** Find cardinality restrictions on properties declared transitive or in chains.
**Fix:** Remove cardinality or transitivity. Use separate simple and transitive properties if both needed.

### R03 — Vacuous Universal ("Only Without Some") `Warning`
**What & Why:** ∀R.C alone is satisfied by individuals with NO R-relationships. "Pizza with only Mozzarella" includes pizzas with no toppings. You almost always need ∃R.C alongside. (Rector et al. 2004)
**Detection:** Find allValuesFrom(P,C) without corresponding someValuesFrom(P,?) on same property.
**Fix:** Add someValuesFrom to establish existence.

### R04 — Existential with Intersection Unsatisfiability `Critical`
**What & Why:** ∃R.(A ⊓ B) where A and B are disjoint — the most common hidden unsatisfiability source.
**Detection:** Find ∃R.(intersectionOf) restrictions and check disjointness of intersection members.
**Fix:** Fix the filler or remove the disjointness.

### R05 — Double Universal with Disjoint Fillers `Critical`
**What & Why:** ∀R.A and ∀R.B where A⊥B — forces R to have no values at all.
**Detection:** Find same-property universal restrictions and check filler disjointness.
**Fix:** Use unionOf: ∀R.(A ∪ B).

### R06 — Existential + Universal with Disjoint Fillers `Critical`
**What & Why:** ∃R.A and ∀R.B where A⊥B — demands an A-filler but requires all fillers to be B. Unsatisfiable.
**Detection:** Same-property existential+universal with disjoint fillers.
**Fix:** Align fillers.

### R07 — No Unique Name Assumption Trap `Warning`
**What & Why:** maxCardinality 1 doesn't reject multiple values — it forces owl:sameAs (identity merging). OWL has no UNA.
**Detection:** Flag maxCardinality 1 where multiple distinct fillers are likely in practice.
**Fix:** Use owl:differentFrom on fillers, or reconsider max cardinality.

### R08 — Missing Functional Declaration `Warning`
**What & Why:** Using maxCardinality 1 per-class instead of declaring the property functional — redundant and fragile.
**Detection:** Name patterns: birthDate, SSN, primaryKey → likely functional.
**Fix:** Replace per-class maxCard 1 with owl:FunctionalProperty. Auto-fixable.

### R09 — Complement Equivalence Trap `Warning`
**What & Why:** C ≡ ¬D makes C contain everything in the universe except D-members. Almost never intended.
**Detection:** Find C ≡ ¬D patterns.
**Fix:** Bound the complement: C ≡ (Parent ⊓ ¬D).

### R10 — Inherited Restriction Conflict `Warning`
**What & Why:** Class C with parents A and B. A says ∀hasColor.Warm, B says ∀hasColor.Cool. If Warm⊥Cool, C can't have any color.
**Detection:** For multiply-inherited classes, collect universal restrictions from all ancestors per property; check filler disjointness.
**Fix:** Weaken one ancestor's restriction or use unionOf.

### R11 — Domain/Range vs. Restriction Mismatch `Warning`
**What & Why:** ∃P.X where X is not a subclass of range(P). Either the range or the restriction is wrong.
**Detection:** For every restriction, check filler compatibility with the property's declared range.
**Fix:** Align filler with range, or update range.

### R12 — Restriction on Wrong Property Type `Warning`
**What & Why:** DatatypeProperty with class filler, or ObjectProperty with XSD filler. Semantically incoherent.
**Detection:** Type-check all restriction property+filler combinations.
**Fix:** Correct the property type. Auto-fixable in some cases.

### R13 — Contradictory Domain Through Restriction `Critical`
**What & Why:** P has domain A. Class B (not subClassOf A) has ∃P.X → B instances inferred as A instances. If A⊥B, unsatisfiable.
**Detection:** For restrictions, verify the class is compatible with the restricted property's domain.
**Fix:** Broaden domain, make B subClassOf A's domain, or use different property.

### R14 — Missing Closure Axioms `Warning`
**What & Why:** Without closure, OWL allows additional values. MargheritaPizza with ∃hasTopping.Mozzarella and ∃hasTopping.Tomato can also have any other topping. (Rector "OWL Pizzas")
**Detection:** LLM + structural: classes with multiple someValuesFrom on same property without allValuesFrom closure.
**Fix:** Add ∀hasTopping.(Mozzarella ∪ Tomato).

### R15 — Flat Restriction Profile (LLM-Specific) `Warning`
**What & Why:** LLMs almost exclusively generate someValuesFrom. Rarely produce allValuesFrom, cardinality, or hasValue.
**Detection:** If 100% restrictions are someValuesFrom and >20 exist, flag.
**Fix:** Review whether universal/cardinality/hasValue restrictions are needed.

### R16 — Existential/Universal Confusion `Critical`
**What & Why:** "some not" (∃R.¬C) ≠ "not some" (¬∃R.C). Vastly different semantics. OOPS! P15.
**Detection:** LLM + structural check for misplaced negation.
**Fix:** Verify intended semantics.

### R17 — Necessary vs. Sufficient Confusion `Critical`
**What & Why:** Class with only subClassOf (necessary conditions) can't be auto-classified. Needs equivalentClass (sufficient conditions). OOPS! P16.
**Detection:** Check classes that should be defined but use only subClassOf.
**Fix:** Convert to equivalentClass using intersectionOf.

### R18 — Over-Specified Genus `Warning`
**What & Why:** In C ≡ (Parent ⊓ restrictions), if restrictions already entail C ⊑ Parent, the genus is redundant (violates DRY). Mungall OntoTip.
**Detection:** Check if restrictions alone imply the stated genus.
**Fix:** Remove redundant genus.

### R19 — Recursive Definition `Warning`
**What & Why:** Class references itself in its own equivalentClass or subClassOf. Almost always unintended. OOPS! P24.
**Detection:** Find self-referencing classes in their own axioms.
**Fix:** Refactor to remove self-reference.

### R20 — GCI on owl:Thing `Warning`
**What & Why:** ⊤ ⊑ ∃hasId.xsd:string forces EVERY individual to have an ID. Clashes with imports. "Highly questionable" — Sattler & Stevens 2012.
**Detection:** Find SubClassOf with complex LHS or owl:Thing as LHS.
**Fix:** Anchor to a specific named class.

### R21 — Hidden GCIs `Warning`
**What & Why:** EquivalentClass(A,C) + SubClassOf(A,D) implicitly encodes GCI C ⊑ D. Protégé reports "hidden GCI count." (Uberon has many.)
**Detection:** Find equivalence+subsumption pairs creating implicit GCIs.
**Fix:** Review whether the implied GCI is intended.

### R22 — Structural Tautologies `Warning`
**What & Why:** A ⊑ ≥0 R.B (always true), A ≡ A, A ⊑ owl:Thing — add no information.
**Detection:** Pattern-match tautological axiom forms.
**Fix:** Remove. Auto-fixable.

---

## 5. Equivalence Class Traps

### E01 — Unintentional Entailed Equivalence `Critical`
**What & Why:** OWL has no Unique Class Assumption. If axioms entail C1 ≡ C2, both stay satisfiable — invisible to standard consistency checking but collapses taxonomy. (Mungall 2018)
**Detection:** Inject a sibling class for every SubClassOf pair, declare disjoint; incoherence reveals unintended equivalence.
**Fix:** Add explicit disjointness or restructure axioms.

### E02 — Equivalence to AllValuesFrom `Critical`
**What & Why:** EquivalentClasses(C, ∀R.D) — any individual NOT in R's domain trivially satisfies the restriction, becoming unintended member of C. Cascades through ontology. (Pellint, Lin & Sirin 2008)
**Detection:** Find EquivalentClasses with AllValuesFrom.
**Fix:** Replace with SubClassOf, or add existential to bound.

### E03 — Equivalence-Disjointness Contradiction `Critical`
**What & Why:** Classes declared both equivalent and disjoint. Always a modeling error — usually meant SubClassOf. Roussey & Corcho (2009) "EID."
**Detection:** Find pairs with both owl:equivalentClass and owl:disjointWith.
**Fix:** Remove the incorrect declaration.

### E04 — Equivalence Chains Across Imports `Warning`
**What & Why:** C1≡C2 in O1 and C2≡C3 in O2 creates transitive C1≡C3 — silently merging concepts across modules.
**Detection:** Trace equivalentClass transitively across imports.
**Fix:** Add explicit disjointness where merging is undesired.

### E05 — Cycle in SubClassOf Without Explicit Equivalence `Critical`
**What & Why:** A ⊑ B and B ⊑ A without EquivalentClasses — creates accidental equivalence. OOPS! P06.
**Detection:** Cycle detection in subClassOf graph.
**Fix:** Declare equivalence explicitly or break the cycle.

### E06 — owl:equivalentClass as Property Misuse `Warning`
**What & Why:** In OWL 2 DL, owl:equivalentClass is axiom syntax, not a property. Using it with SubPropertyOf silently degrades to annotation. (Mungall 2021)
**Detection:** Check for property-level usage of owl:equivalentClass.
**Fix:** Use proper EquivalentClasses axiom syntax.

---

## 6. Naming & Labeling

### N01 — Inconsistent Casing Convention `Warning`
**What & Why:** Mixed casing (snake_case, camelCase, kebab-case) looks unprofessional and causes tool errors. OOPS! P22.
**Detection:** Check all names against dominant convention. Classes: UpperCamelCase; properties: lowerCamelCase.
**Fix:** Standardize. Auto-fixable.

### N02 — Plural Class Names `Warning`
**What & Why:** Classes represent concepts, not collections. "Animals" should be "Animal." OBO/W3C convention.
**Detection:** Flag names ending in "s" that appear plural (NLP/heuristic).
**Fix:** Rename to singular. Auto-fixable.

### N03 — Instance-Like Class Names `Warning`
**What & Why:** Proper nouns, dates, serial numbers suggest these should be individuals.
**Detection:** NER + heuristic for proper nouns, dates, specific identifiers.
**Fix:** Convert to individuals.

### N04 — Vague/Generic Names `Warning`
**What & Why:** "Entity", "Object", "Data", "Info" provide no domain information.
**Detection:** Blocklist: Thing, Object, Entity, Concept, Item, Element, Resource, Misc, Other, General, Abstract, Base, Data, Info, Stuff.
**Fix:** Replace with domain-specific names.

### N05 — Missing Labels/Annotations `Warning`
**What & Why:** Entities without labels are incomprehensible to users. Missing comments = no documentation. OOPS! P08.
**Detection:** Flag entities with no rdfs:label or rdfs:comment.
**Fix:** Add labels and comments. Auto-fixable for labels from local names.

### N06 — Abbreviations Without Expansion `Warning`
**What & Why:** Domain jargon that may be incomprehensible to outsiders.
**Detection:** Flag sequences of 2+ capitals or short names <4 chars without expanding label/comment.
**Fix:** Add full-name rdfs:label or comment.

### N07 — Property Naming Convention Violations `Warning`
**What & Why:** Object properties should be verb phrases (hasX, isXOf); datatype properties noun phrases. "color" is ambiguous.
**Detection:** Pattern-match property names against conventions.
**Fix:** Rename following conventions.

### N08 — Duplicate Labels `Warning`
**What & Why:** Distinct entities with same label cause ambiguity. OOPS! P32.
**Detection:** Group entities by rdfs:label.
**Fix:** Add disambiguating qualifiers.

### N09 — Labels Containing Hierarchy Information `Warning`
**What & Why:** "Animal - Mammal - Dog" duplicates structural info, creates maintenance burden.
**Detection:** Flag labels with path separators or parent names.
**Fix:** Simplify to "Dog." Auto-fixable.

### N10 — Redundant Namespace in Local Name `Warning`
**What & Why:** pizza:PizzaTopping — "Pizza" is already in the namespace.
**Detection:** Flag local names repeating the namespace/prefix.
**Fix:** Shorten local names.

### N11 — Swapped Annotation Contents `Warning`
**What & Why:** rdfs:label longer than rdfs:comment, or label contains sentences. OOPS! P20.
**Detection:** Flag if label.length > comment.length or label contains periods/sentences.
**Fix:** Swap values. Auto-fixable.

---

## 7. Redundancy & Duplication

### D01 — Redundant SubClassOf (Transitive Reduction) `Warning`
**What & Why:** A ⊑ B and B ⊑ C makes A ⊑ C redundant. Bloats ontology; changes to B may not propagate correctly.
**Detection:** Compute transitive reduction. Any asserted edge already entailed is redundant.
**Fix:** Remove redundant edges. Auto-fixable via ROBOT reduce.

### D02 — Redundant EquivalentClass + SubClassOf `Warning`
**What & Why:** EquivalentClasses(A,B) already implies both SubClassOf directions.
**Detection:** Find pairs with both equivalence and subsumption.
**Fix:** Remove the redundant SubClassOf. Auto-fixable.

### D03 — Semantically Equivalent Classes `Warning`
**What & Why:** Classes meaning the same thing but without owl:equivalentClass. Queries miss data. OOPS! P02.
**Detection:** Embedding similarity >0.9 + structural similarity (Jaccard over property signatures) >0.85.
**Fix:** Merge or declare equivalentClass.

### D04 — Semantically Equivalent Properties `Warning`
**What & Why:** Duplicate properties fragment data.
**Detection:** Embedding similarity >0.9 + matching domain/range.
**Fix:** Merge or declare equivalentProperty.

### D05 — Near-Duplicate Class Definitions `Warning`
**What & Why:** Almost-identical axiom signatures suggest accidental duplication.
**Detection:** Jaccard similarity >0.8 over axiom signatures.
**Fix:** Merge or add distinguishing axioms.

### D06 — Duplicate Hierarchies `Warning`
**What & Why:** Parallel isomorphic subtrees (e.g., ProductType tree mirroring Product tree) — maintenance nightmare.
**Detection:** Detect isomorphic subtrees.
**Fix:** Collapse into single hierarchy using properties or defined classes.

### D07 — Synonyms as Separate Classes `Warning`
**What & Why:** "Car" and "Automobile" as distinct classes fragment the ontology.
**Detection:** Embedding distance <0.1. Check for abbreviation/acronym relationships.
**Fix:** Merge into one class with skos:altLabel.

---

## 8. Modeling Pattern Violations

### M01 — God Class `Warning`
**What & Why:** Class with >15–20 associated properties — conflates multiple concerns. Hard to understand, maintain, reuse.
**Detection:** Count properties per class. Flag >2σ above mean.
**Fix:** Decompose into smaller classes.

### M02 — Datatype-Only Class `Warning`
**What & Why:** Class with only datatype properties and no object property connections — an isolated value object.
**Detection:** Find classes with zero object property participation.
**Fix:** Connect via object properties or model as complex datatype.

### M03 — Enumeration vs. Subclass Confusion `Warning`
**What & Why:** Small/Medium/Large as subclasses when owl:oneOf enumeration is more appropriate. W3C Value Partitions pattern.
**Detection:** Flag classes with 3–10 leaf subclasses all lacking unique properties.
**Fix:** Convert to enumeration or value partition pattern.

### M04 — N-ary Relation Modeled as Binary `Warning`
**What & Why:** Binary properties can't capture multi-argument relationships. "teaches(Prof, Course)" can't encode semester or grade.
**Detection:** LLM identifies co-occurring binary properties that share contextual parameters.
**Fix:** Introduce reification class (TeachingAssignment) linking all participants.

### M05 — Missing Reification Opportunities `Warning`
**What & Why:** Properties needing temporal scope, provenance, or qualifiers can't carry this as binary relations.
**Detection:** LLM assesses each property for contextual information needs.
**Fix:** Apply reification or TimeIndexedSituation pattern.

### M06 — Lazy Primitive Ratio `Warning`
**What & Why:** Healthy ontologies have 30–60%+ defined classes (with equivalentClass). 0% = pure taxonomy with no reasoning benefit. (Rector normalization)
**Detection:** defined_classes / total_classes.
**Fix:** Add equivalentClass definitions for automatic classification.

### M07 — Missing Part-Whole Patterns `Warning`
**What & Why:** Domains with natural components (Body/Organs, Building/Rooms) but no partOf/hasPart properties.
**Detection:** LLM + name patterns for composite domain concepts.
**Fix:** Add partOf/hasPart with appropriate transitivity.

### M08 — Duplicating Built-In Datatypes `Warning`
**What & Why:** Classes like "StringValue" or "DateValue" reinventing XSD datatypes as class hierarchies. OOPS! P23.
**Detection:** Class names mirroring XSD type names.
**Fix:** Replace with datatype properties using XSD types.

### M09 — Using "is" Relation Instead of OWL Primitives `Critical`
**What & Why:** A manually created "is" or "isA" property instead of rdfs:subClassOf or rdf:type. Bypasses OWL semantics. OOPS! P03.
**Detection:** Find properties named is, isA, is_a, type, instanceof.
**Fix:** Replace with OWL primitives. Auto-fixable.

### M10 — Compound Names Without Matching Restrictions `Warning`
**What & Why:** "RedWine" without ∃hasColor.Red — name-only classification with no logical basis. (Mungall OntoTip)
**Detection:** LLM flags compound names where modifier isn't reflected in any restriction.
**Fix:** Add restrictions matching name components.

---

## 9. OWL Semantics Traps

### O01 — Open World Assumption Bias `Warning`
**What & Why:** Comments say "only three subtypes" but no closure axioms exist. OWL allows unlimited additional subtypes regardless. (Mungall 2020)
**Detection:** LLM reviews restrictions and comments for closed-world language not reflected in axioms.
**Fix:** Add disjointness, closure axioms, or owl:oneOf.

### O02 — OWL 2 DL Global Restriction Violations `Critical`
**What & Why:** 12 forbidden patterns (Rudolph et al. arXiv:1212.2902): transitive+cardinality, non-simple in disjoint/irreflexive, etc. Makes reasoning undecidable.
**Detection:** Check all axioms against the 12 patterns. ARGO tool.
**Fix:** Restructure to comply.

### O03 — Uncontrolled Punning `Warning`
**What & Why:** Same IRI as both class and individual without documentation. Legal in OWL 2 but confusing.
**Detection:** Find IRIs used as both owl:Class and owl:NamedIndividual without annotation.
**Fix:** Document explicitly or use separate IRIs.

### O04 — Profile-Breaking Construct Interaction `Warning`
**What & Why:** An ontology appears EL-compatible but violates it after normalization (e.g., DisjointClasses expanding to contain ComplementOf). ARGO (Matentzoglu 2017).
**Detection:** Full profile compliance check including normalization.
**Fix:** Apply complexity downgrading transformations (Šváb-Zamazal et al.).

### O05 — Expressivity Gap `Warning`
**What & Why:** Using SROIQ constructs when EL/RL would suffice means unnecessarily slow reasoning.
**Detection:** Compute OWL 2 expressivity profile; identify constructs causing the bump.
**Fix:** Replace with simpler alternatives where possible.

### O06 — SubClassOf ≠ ProperSubClassOf `Warning`
**What & Why:** OWL's SubClassOf means ⊆ (allows equality). There is no strict ⊂ in OWL. Without disjointness, reasoner may infer equivalence.
**Detection:** See E01 — inject sibling + disjointness to reveal unintended equivalence.
**Fix:** Add disjointness between siblings.

---

## 10. Property Chain Issues

### PC01 — Chain Domain/Range Incompatibility `Critical`
**What & Why:** In R1 ∘ R2 ⊑ S: if range(R1) is incompatible with domain(R2), the chain can never fire. Dead chain. (Keet ProChainS)
**Detection:** Verify range(R1) ⊆ domain(R2), domain(R1) ⊆ domain(S), range(R2) ⊆ range(S).
**Fix:** Fix domain/range or restructure chain.

### PC02 — Unintended Transitivity Inheritance `Warning`
**What & Why:** "directPartOf" as sub-property of transitive "partOf" inherits transitive behavior. The "direct" semantics is lost. (Keet SubProS, EKAW 2012)
**Detection:** Check sub-properties of transitive properties.
**Fix:** Model independently rather than as sub-property.

### PC03 — Circular Property Chain `Critical`
**What & Why:** R ∘ S ⊑ R where R appears in its own chain. Violates OWL 2 regularity; makes reasoning undecidable.
**Detection:** Detect super-property appearing in its own chain definition.
**Fix:** Break circularity with auxiliary properties.

### PC04 — Missing Useful Property Chains `Info`
**What & Why:** Useful chains that could be defined but aren't (e.g., uncle = parent ∘ brother).
**Detection:** From instance triples or expected usage, detect frequent 2-hop paths.
**Fix:** Add chain axioms for frequently traversed patterns.

### PC05 — Single-Element Property Chain `Warning`
**What & Why:** A chain with one element = subPropertyOf in complex syntax. OOPS! P33.
**Detection:** Find propertyChainAxioms with only one property.
**Fix:** Replace with subPropertyOf. Auto-fixable.

---

## 11. Datatype Property Issues

### DT01 — String-as-Enumeration `Warning`
**What & Why:** Free-text strings for fixed vocabularies (status, priority, color). Allows typos, prevents reasoning.
**Detection:** xsd:string properties with ≤10 distinct values or names suggesting closed sets.
**Fix:** Model as owl:oneOf enumeration or value partition.

### DT02 — String-as-Object-Property `Warning`
**What & Why:** Storing entity references as strings prevents relationship traversal.
**Detection:** xsd:string properties whose values are consistently URIs or entity identifiers.
**Fix:** Convert to object property.

### DT03 — Boolean-as-Class `Warning`
**What & Why:** VegetarianDish/NonVegetarianDish subclasses for a boolean distinction.
**Detection:** LLM + heuristic: two sibling subclasses representing true/false states.
**Fix:** Consider boolean datatype property if simpler modeling suffices.

### DT04 — Language-Tagged vs. Plain String Confusion `Warning`
**What & Why:** "Dog"@en ≠ "Dog"^^xsd:string in RDF. Mixing causes SPARQL filter failures.
**Detection:** Find properties mixing language-tagged and untagged strings.
**Fix:** Standardize on one approach (language-tagged preferred).

### DT05 — Unconstrained Numeric Ranges `Warning`
**What & Why:** "age" as xsd:integer allows negatives. Temperature in Kelvin below 0. Percentages above 100.
**Detection:** LLM flags numeric properties where domain implies constraints.
**Fix:** Use xsd:nonNegativeInteger or add facet restrictions.

### DT06 — Date/Time Type Mixing `Warning`
**What & Why:** xsd:string for dates, or inconsistent xsd:date / xsd:dateTime usage.
**Detection:** Find string properties with date-like values; find mixed date types.
**Fix:** Standardize on xsd:date or xsd:dateTime.

---

## 12. Annotation & Documentation

### A01 — Inconsistent Language Tags `Warning`
**Detection:** Find annotations mixing @en, @en-US, @en-GB, and untagged on same properties.
**Fix:** Standardize. Auto-fixable.

### A02 — Annotation Property Overloading `Warning`
**What & Why:** rdfs:comment used for definitions, usage notes, provenance, and editorials simultaneously.
**Detection:** Flag if >50% of comments exceed 2 sentences or contain structured content.
**Fix:** Use skos:definition, skos:scopeNote, skos:editorialNote, dc:source.

### A03 — Multiple Definitions `Warning`
**What & Why:** Entities with >1 definition annotation. Violates OBO Foundry convention.
**Detection:** Flag >1 rdfs:comment or IAO:definition per entity.
**Fix:** Consolidate into single authoritative definition.

### A04 — Annotation Whitespace `Warning`
**What & Why:** Leading/trailing spaces, double spaces, tabs. Breaks SPARQL matching. ROBOT ERROR-level.
**Detection:** Regex for whitespace anomalies.
**Fix:** Trim. Auto-fixable.

### A05 — Misleading Comments Contradicting Axioms `Warning`
**Detection:** LLM compares rdfs:comment text with actual axioms per class. Flags contradictions.
**Fix:** Update axioms to match intent, or correct comments.

### A06 — Missing Provenance `Warning`
**What & Why:** No dc:source, dc:creator, prov:wasDerivedFrom. MIRO: ~11% pass. Prevents trust assessment.
**Detection:** Check for provenance annotations.
**Fix:** Add dc:creator, dc:date, dc:source, owl:versionInfo.

### A07 — Missing owl:Ontology Declaration `Warning`
**What & Why:** No identity, versioning, or import management. OOPS! P38.
**Detection:** Check for owl:Ontology with versionIRI, metadata, imports.
**Fix:** Add owl:Ontology declaration.

---

## 13. Import & Alignment

### I01 — Ontology Hijacking `Critical`
**What & Why:** Asserting axioms about terms in namespaces you don't own. Changes external semantics. (Hogan et al. 2010)
**Detection:** Find axioms about terms in external namespaces.
**Fix:** Use local subclasses referencing external terms via restrictions.

### I02 — Soft Reuse Without Import `Warning`
**What & Why:** Using external URIs without owl:imports — name without meaning. ~50% of reuse is "soft." (LOV statistics)
**Detection:** Find external namespace URIs without corresponding imports.
**Fix:** Add owl:imports or copy needed axioms with attribution.

### I03 — Using Undefined Properties/Classes `Warning`
**What & Why:** 14.3% of RDF triples reference undeclared terms. No OWL semantics apply. OOPS! P34, P35.
**Detection:** Find URIs used in axioms without owl:Class/Property declarations.
**Fix:** Add declarations or import defining ontology.

### I04 — IRI Reference Errors `Warning`
**What & Why:** HTTP/HTTPS mismatches, typos, non-resolving version strings. (Kamdar et al.)
**Detection:** Edit-distance from known ontology URIs; HTTP resolution check.
**Fix:** Correct IRIs. Use content negotiation.

### I05 — Namespace Collision `Warning`
**What & Why:** Local entities accidentally using external namespace URIs.
**Detection:** Compare local entity IRIs against known external namespaces.
**Fix:** Use distinct local namespace.

### I06 — Conservativity Principle Violation `Critical`
**What & Why:** Alignment introduces novel subsumption within input ontologies. Unintended semantic commitments. (Solimando et al. ISWC 2014)
**Detection:** After merge, check for new subsumption between concepts within each input ontology.
**Fix:** Remove violating mappings. Alcomo tool can detect and repair.

### I07 — Non-Conservative Extension `Critical`
**What & Why:** Adding axioms changed the meaning of existing concepts. Existing queries return different results. (Ghilardi, Lutz, Wolter KR 2006)
**Detection:** Check if any consequence over T1's vocabulary follows from T1∪T2 but not T1 alone.
**Fix:** Restructure extension or document semantic changes.

---

## 14. Cross-Cutting Concern Entanglement

### CC01 — Temporal Baking `Warning`
**What & Why:** FormerEmployee, CurrentStudent as classes instead of temporal properties with dates.
**Detection:** Regex: Former*, Current*, Past*, Ex*, Previous*, Future*, Upcoming*.
**Fix:** Use TimeIndexedSituation pattern with start/end dates.

### CC02 — Spatial Baking `Warning`
**What & Why:** NorthRegionStore, DowntownBranch as classes instead of location properties.
**Detection:** Regex: North*, South*, Downtown*, Remote*, Local*, Offshore*.
**Fix:** Model via hasLocation property.

### CC03 — Status Baking `Warning`
**What & Why:** ActiveSubscription, CancelledSubscription as subclasses instead of hasStatus property.
**Detection:** Sibling classes sharing root with Active*, Inactive*, Pending*, Cancelled*, Expired*, Draft*.
**Fix:** Model as hasStatus → Status enumeration.

### CC04 — Measure Baking `Warning`
**What & Why:** weightInKilograms, priceInUSD instead of measurement pattern (value + unit).
**Detection:** Regex: *InKg, *InUSD, *InCelsius, *InMeters, *PerHour.
**Fix:** Use Measurement class with hasValue + hasUnit.

---

## 15. Meta-Level & Level Mixing

### ML01 — Meta-Level Contamination `Warning`
**What & Why:** OntologyModule, ClassificationScheme as siblings of Person, Vehicle. Different ontological levels.
**Detection:** LLM flags meta-ontological names among domain classes.
**Fix:** Separate into distinct module or use annotations.

### ML02 — Metaclass Confusion `Warning`
**What & Why:** Species with instances like Eagle, where Eagle is also a class with instances. Ambiguous.
**Detection:** Find IRIs used as both class and instance of another class.
**Fix:** Use proper metaclass patterns with documentation.

---

## 16. Intent Alignment

### IA01 — Domain Vocabulary Mismatch `Warning`
**What & Why:** Terms not belonging to the domain — "WeatherCondition" in a restaurant ontology.
**Detection:** Embedding centroid of all names; flag entities >2σ from centroid.
**Fix:** Remove out-of-domain entities.

### IA02 — Scope Creep `Warning`
**What & Why:** Ontology contains concepts beyond requirements. Common in LLM generation.
**Detection:** LLM compares content against user prompt/requirements.
**Fix:** Remove unjustified entities.

### IA03 — Superfluous Class Padding (LLM-Specific) `Warning`
**What & Why:** LLMs generate extra classes no requirement asks for, with no properties or axiom participation.
**Detection:** Flag classes failing ALL: not in requirements, not in any restriction, not domain/range, not in prompt.
**Fix:** Remove.

### IA04 — Textbook Pattern Mismatch (LLM-Specific) `Warning`
**What & Why:** Every LLM ontology gets Agent→Person/Organization, Event→hasParticipant even for "coffee bean processing."
**Detection:** LLM checks top-level classes against generic-pattern blocklist for domain relevance.
**Fix:** Remove unwarranted upper-level classes. Import standard upper ontology if alignment desired.

---

## 17. Change History & Evolution

### CH01 — Orphaned References After Deletion `Critical`
**What & Why:** Deleting a class without updating references leaves dangling pointers. Causes reasoner errors.
**Detection:** After deletion, scan all axioms for references to deleted IRIs.
**Fix:** Cascade deletions. ROBOT's remove command. Auto-fixable.

### CH02 — Oscillating Changes `Warning`
**What & Why:** Entity added, removed, re-added — indicates modeling uncertainty.
**Detection:** Track add-remove-add patterns in change history.
**Fix:** Resolve and document the design decision.

### CH03 — Rename Shadows `Warning`
**What & Why:** New entity similar to recently deleted one — rename done by delete+create, losing history.
**Detection:** Embedding similarity >0.85 between new and recently deleted entities.
**Fix:** Use proper rename/refactor operations.

### CH04 — Monotonicity Violation `Warning`
**What & Why:** In monotonic OWL, adding axioms should only add entailments. If entailments are lost, axioms were deleted — may break backward compatibility. (Haase & Stojanovic ESWC 2005)
**Detection:** Compare entailments before and after edit.
**Fix:** Document and justify axiom removals.

### CH05 — Effectual vs. Ineffectual Change Ratio `Info`
**What & Why:** High ratio of semantically vacuous changes = noisy editing. (Gonçalves et al. 2011–2014, 88 NCI Thesaurus versions)
**Detection:** Classify edits as effectual (changes deductive closure) vs. ineffectual.
**Fix:** Focus review on effectual changes.

### CH06 — Drift Detection `Warning`
**What & Why:** Ontology gradually drifts from original purpose through accumulation of edits.
**Detection:** Embedding centroid distance from original prompt across versions.
**Fix:** Periodically review against requirements.

---

## 18. Reasoning Performance Anti-Patterns

### RP01 — Explicit GCI Performance Trap `Warning`
**What & Why:** SubClassOf with complex LHS → internally converted to universal nondeterministic check on every individual. Extremely expensive for tableau reasoners. (Pellint, Lin & Sirin 2008)
**Detection:** Find SubClassOf with complex (intersection/union/restriction) left-hand side.
**Fix:** Rewrite with named classes on LHS.

### RP02 — Implicit GCI Performance Trap `Warning`
**What & Why:** EquivalentClasses(C, A⊓B) + SubClassOf(C, ∃R.D) creates implicit GCI with same cost.
**Detection:** Detect equivalence+subsumption pairs creating implicit GCIs.
**Fix:** Replace equivalence with SubClassOf if auto-classification not needed.

### RP03 — Existential Explosion `Warning`
**What & Why:** Interconnected someValuesFrom + cardinality forces creation of intractable numbers of tableau witnesses.
**Detection:** Estimate total witnesses from interconnected restrictions. Pellint computes this.
**Fix:** Reduce cardinality values, simplify nesting, or use EL-compatible patterns.

### RP04 — Large Disjunction `Warning`
**What & Why:** UnionOf with >5 operands multiplies nondeterministic branching exponentially.
**Detection:** Flag UnionOf with >5 operands.
**Fix:** Refactor using intermediate named classes.

### RP05 — Large Cardinality Restrictions `Warning`
**What & Why:** exactCardinality(50) creates 50 witnesses per individual during reasoning.
**Detection:** Flag min/max/exact cardinality with values >10.
**Fix:** Reduce if approximation acceptable.

---

## 19. Information-Theoretic & Evaluation Metrics

### IT01 — Intrinsic Information Content Imbalance `Info`
**What & Why:** Skewed IC among siblings = hierarchy imbalance. One sibling has 50 children, another has 1. (Seco et al. 2004)
**Detection:** IC(c) = −log((hyponyms(c)+1) / max_nodes). Flag sibling groups with IC variance >2σ.
**Fix:** Balance by expanding under-differentiated branches.

### IT02 — Shannon Entropy of Hierarchy `Info`
**What & Why:** Single number for overall balance. High = balanced; low = degenerate/skewed. (Calmet & Daemi 2004)
**Detection:** Compute entropy over class probability distribution from connectivity.
**Fix:** Target moderate entropy.

### IT03 — Relation Entropy `Info`
**What & Why:** Low entropy = dominated by single relation type (is-a only) = semantically impoverished.
**Detection:** H = −Σ p(r) log p(r) for relation type distribution.
**Fix:** Add object properties for non-taxonomic relationships.

### IT04 — Relationship Richness (OntoQA) `Info`
**What & Why:** RR = |P| / (|P| + |IsA|). RR ≈ 0 = pure taxonomy; RR ≈ 1 = rich property network. (Tartir et al. 2005)
**Detection:** Compute ratio.
**Fix:** Increase RR by adding object properties.

### IT05 — Deductive Closure Gap `Info`
**What & Why:** Asserted = inferred hierarchy → reasoner adds nothing (0% value). Huge gap → under-constrained. Both extremes problematic. (Vrandečić & Sure)
**Detection:** Compare asserted vs. inferred graph.
**Fix:** If zero gap: add defined classes and restrictions. If huge: verify all inferences are intended.

### IT06 — OQuaRE Quality Score `Info`
**What & Why:** ISO/IEC 25000 SQuaRE adapted to ontologies. 14 metrics across 7 quality characteristics. Standardized comparison. (Duque-Ramos et al. 2011)
**Detection:** Compute OQuaRE metrics.
**Fix:** Target specific quality characteristic improvements.

---

## 20. Community-Specific Checks

### CS01 — Equivalent Pair (OBO ROBOT) `Critical`
**What & Why:** Reasoner infers mutual SubClassOf not explicitly declared as equivalent. 99.9% unintended.
**Detection:** Run reasoner; check for entailed equivalences not in asserted axioms.
**Fix:** Review causing axioms and fix the erroneous one.

### CS02 — Misused Obsolete Label (OBO ROBOT) `Warning`
**Detection:** Flag owl:deprecated classes still in active axioms.
**Fix:** Replace with recommended replacements.

### CS03 — Missing Textual Definitions (OBO FP06) `Warning`
**What & Why:** ~11% of OBO ontologies pass this check. Every class needs a human-readable definition.
**Detection:** Flag classes without IAO:definition or rdfs:comment.
**Fix:** Add definitions. LLM can draft from axioms.

### CS04 — Singleton Structural Pattern (SNOMED) `Warning`
**What & Why:** A class with a unique axiom structure across the entire ontology — 92% reveal modeling problems. (Lopez-Garcia & Schulz, PLOS ONE 2016)
**Detection:** Hash axiom patterns per class; flag unique patterns.
**Fix:** Compare against structurally similar classes for expected patterns.

### CS05 — Inverse Property Proliferation (gist) `Warning`
**What & Why:** >50% properties having inverses doubles the space without reasoning benefit. SPARQL navigates inverses without explicit declarations.
**Detection:** Count inverse declarations as ratio of total properties.
**Fix:** Remove unnecessary inverses. Use SPARQL paths.

### CS06 — Distinctionary Pattern Violation (Semantic Arts) `Warning`
**What & Why:** Sibling subclasses differing only in name, not axioms — "names without meaning."
**Detection:** LLM + deterministic: siblings lacking any distinguishing restriction.
**Fix:** Add distinguishing restrictions or merge.

### CS07 — TBox/ABox Mixing `Warning`
**What & Why:** Schema and data in same file — different update frequencies and governance.
**Detection:** Find NamedIndividual declarations in a TBox ontology.
**Fix:** Separate into distinct files.

### CS08 — RelRig: Relator Mediating Rigid Types (OntoUML) `Warning`
**What & Why:** Most frequent OntoUML anti-pattern (282 occurrences in 54 models). One participant likely misclassified.
**Detection:** LLM + OntoClean rigidity check on relator participants.
**Fix:** Reclassify one participant as role.

### CS09 — FreeRole (OntoUML) `Warning`
**What & Why:** Role without explicit relator — defining relationship is unmodeled. (119 occurrences)
**Detection:** LLM identifies roles lacking relator classes.
**Fix:** Add explicit relator.

### CS10 — MultDep: Multiple Relator Dependencies (OntoUML) `Warning`
**What & Why:** Role depending on multiple relators may represent two distinct roles. (105 occurrences)
**Detection:** LLM identifies roles with multiple relator dependencies.
**Fix:** Split role or merge relators.

---

## 21. Instance Population Readiness

### IP01 — Circular Instantiation Dependency `Warning`
**What & Why:** A requires ∃R.B and B requires ∃S.A — can't create either without the other.
**Detection:** Build "requires" graph from existential restrictions; find cycles.
**Fix:** Weaken one restriction or define a creation protocol.

### IP02 — Overly Strict Class `Warning`
**What & Why:** ≥5 independent restrictions making the class pragmatically empty — technically satisfiable but unrealistic.
**Detection:** Count non-inherited restrictions per class. LLM assesses pragmatic feasibility.
**Fix:** Relax overly demanding constraints.

### IP03 — Missing Identity Properties `Warning`
**What & Why:** Person, Product, Order without any functional/inverse-functional property — deduplication impossible.
**Detection:** For non-abstract classes likely to have instances, check for at least one identifying property.
**Fix:** Add functional datatype property or inverse-functional property.

---

## 22. Refactoring Opportunities

### RF01 — Property Lifting (Pull-Up) `Info`
**What & Why:** Dog ⊑ ∃hasOwner.Person, Cat ⊑ ∃hasOwner.Person, Rabbit ⊑ same — should be on superclass Pet.
**Detection:** For each property+filler, find all classes asserting it. If ≥N share a parent lacking the restriction, flag.
**Fix:** Lift restriction to common superclass. Auto-fixable.

### RF02 — Common Restriction Extraction `Info`
**What & Why:** Several unrelated classes share identical complex restrictions but have no shared named class.
**Detection:** Hash restriction patterns; group classes by shared patterns; ≥3 classes sharing ≥2 restrictions without shared superclass.
**Fix:** Extract a named superclass for the shared restrictions.

### RF03 — Parallel Property Consolidation `Info`
**What & Why:** teachesUndergrad, teachesGrad, teachesPhD differ only in range specialization.
**Detection:** Properties sharing name stem + same domain + range differs by sibling classes.
**Fix:** One "teaches" property with range restrictions per class.

---

*Sources: OOPS! 41-pitfall catalog (Poveda-Villalón 2016), OntoClean (Guarino & Welty), Rector et al. "OWL Pizzas" (EKAW 2004), Keet SubProS/ProChainS (EKAW 2012), Pellint (Lin & Sirin, OWLED 2008), Roussey & Corcho anti-pattern catalog (K-CAP 2009), Sales & Guizzardi OntoUML (DKE 2015), Lopez-Garcia & Schulz SNOMED (PLOS ONE 2016), Hoser et al. graph analysis (ESWC 2006), Vrandečić & Sure metrics, Kalyanpur et al. (JWS 2005), Schlobach & Cornet (IJCAI 2003), Horridge et al. justifications (ISWC 2008-2013), Bail et al. (OWLED 2010), Mungall OntoTips, Semantic Arts gist, ROBOT/OBO Foundry, Solimando et al. conservativity (ISWC 2014), Ghilardi et al. (KR 2006), Seco et al. IC (2004), Tartir et al. OntoQA (2005), Duque-Ramos et al. OQuaRE (2011), Matentzoglu ARGO (2017), Ontogenia/ESWC 2025, Zhao et al. LLM-OntoClean (2024).*
