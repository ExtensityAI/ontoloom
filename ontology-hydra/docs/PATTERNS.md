# Ontology Design Patterns

Curated patterns applicable to the current model (classes, properties, hierarchy — no restrictions or defined classes). Each pattern maps to specific diagnostics and provides a concrete modeling template.

For how patterns inform resolution, see [RESOLUTION.md](RESOLUTION.md) § Hints as Skills. For the diagnostic catalog, see [CATALOG.md](CATALOG.md).

---

## How Patterns Are Used

- **Bootstrap:** The agent applies patterns when recognizing domain structures during seed generation. "This domain has people with roles" → apply Role Separation from the start.
- **Resolution hints:** When a diagnostic maps to a pattern, the resolution subagent receives the pattern as a fix template — concrete and well-defined, less room for improvisation.
- **Decision anchoring:** Decisions that apply a pattern reference it by name. "Applied P.01 Role Separation for Student (per T04)" is clearer than "chose option B."

Patterns are included in the agent's prompt context as modeling knowledge — always-available reference, not a tool to look up.

---

## Rigidity Backbone

Before applying individual patterns, the agent should identify the **rigidity backbone** of the ontology — the stable structural core that everything else builds on. This principle, drawn from OntoClean (Guarino & Welty, 2002), is the single most important guide for making good structural decisions early.

### OntoClean Metaproperties (Simplified)

| Metaproperty | Question | Examples |
|---|---|---|
| **Rigid (+R)** | Can an instance lose membership without ceasing to exist? No → rigid. | Person, Vehicle, Building, River |
| **Anti-rigid (~R)** | Must instances be able to leave the class? Yes → anti-rigid. | Student, Driver, Manager, Patient |
| **Semi-rigid** | Some instances can leave, some can't. | Rare; treat as anti-rigid for safety. |

**The constraint:** An anti-rigid class cannot subsume a rigid class. If Student is anti-rigid and Person is rigid, then `Student subClassOf Person` violates this constraint — it implies every person is necessarily a student. This is exactly what T04 detects.

### Application

During bootstrap and Phase 1 decisions:

1. **Identify rigid classes first.** These are the top-level branches: natural kinds, physical objects, locations, events, organizations. They form the stable backbone that rarely needs restructuring.
2. **Model anti-rigid concepts via patterns, not subClassOf.** Roles (Student, Driver, Manager) use P.01 Role Separation. Phases (ActiveSubscription, ExpiredContract) use P.08 Cross-Cutting Separation. Constituted objects (WoodTable) use P.03 Constitution.
3. **When unsure, default to rigid.** If you can't determine rigidity, treat the class as rigid and place it in the backbone. It's cheaper to later extract an anti-rigid concept from the backbone (move it to a role pattern) than to discover that a backbone class was actually anti-rigid (requires restructuring everything built on top of it).

The rigidity backbone is not a formal module boundary — it's a design heuristic that makes early structural decisions more likely to survive the full diagnostic loop.

### Sources

- Guarino, N. and Welty, C. "Evaluating Ontological Decisions with OntoClean" (CACM 2002)
- Guarino, N. and Welty, C. "An Overview of OntoClean" (Handbook on Ontologies, 2004/2009)
- Welty, C. "OntOWLClean: Cleaning OWL Ontologies with OWL" (FOIS 2006)

---

## Pattern Catalog

### P.01 — Role Separation

**Problem:** A role (anti-rigid concept) modeled as a subclass of a rigid concept. "Student subClassOf Person" — a person can stop being a student without ceasing to exist.

**Diagnostics:** T04, T11

**Template:**
```turtle
:Student a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "The role of being enrolled in an educational program" .

:hasRole a owl:ObjectProperty ;
    rdfs:domain :Person ;
    rdfs:range :Student ;
    rdfs:comment "A role currently held by this person" .
```

**Key decision:** Are roles grouped under a Role superclass or modeled as top-level classes? Both valid — depends on whether roles need their own hierarchy.

**Model limitation:** Without restrictions, we can't enforce "every Student must be played by a Person." The domain/range on hasRole provides soft guidance.

---

### P.02 — Part-Whole (Mereology)

**Problem:** A component modeled as a subclass instead of a part. "Engine subClassOf Car" — an engine is not a kind of car.

**Diagnostics:** T02, M07

**Template:**
```turtle
:Engine a owl:Class ;
    rdfs:subClassOf :Component ;
    rdfs:comment "The primary power source of a vehicle" .

:hasPart a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Component ;
    rdfs:comment "A physical component of this vehicle" .

:isPartOf a owl:ObjectProperty ;
    rdfs:domain :Component ;
    rdfs:range :Vehicle ;
    owl:inverseOf :hasPart ;
    rdfs:comment "The vehicle this component belongs to" .
```

**Variants:** hasPart/isPartOf for composition; hasMember/isMemberOf for collections; hasIngredient for mixtures. Use the most specific variant that applies.

**Key decision:** Should parts have their own class hierarchy (Component → Engine, Chassis) or sit flat? Hierarchy is better when parts have distinct properties.

---

### P.03 — Constitution (Material)

**Problem:** An object modeled as a subclass of its material. "WoodTable subClassOf Wood" — a table is not a kind of wood.

**Diagnostics:** T03

**Template:**
```turtle
:Table a owl:Class ;
    rdfs:subClassOf :Furniture ;
    rdfs:comment "A flat-topped piece of furniture" .

:madeOf a owl:ObjectProperty ;
    rdfs:domain :Furniture ;
    rdfs:range :Material ;
    rdfs:comment "The primary material this item is constructed from" .
```

**Key decision:** Model materials as classes (Wood, Metal, Composite) or as a datatype property (materialType: string)? Classes when materials have their own properties (density, cost); datatype when they're just labels.

---

### P.04 — Classification (Class vs. Instance)

**Problem:** A specific individual modeled as a class. "IBM subClassOf Company" — IBM is a specific company, not a kind of company.

**Diagnostics:** T01, T05, N03

**Resolution:** The current model has no ABox (no individuals). When detected, the fix is removal from the class hierarchy. The entity belongs in instance data, not the TBox.

If the ontology needs to reference specific well-known entities as classification anchors (e.g., reference materials, standard units), document this explicitly in the class description: "Reference instance retained as class for classification purposes."

---

### P.05 — N-ary Relation (Reification)

**Problem:** A relationship that needs more than two participants or has contextual attributes, modeled as a simple binary property.

**Diagnostics:** M04, M05

**Template:**
```turtle
# Instead of: :teaches linking :Professor to :Course
# When we also need: semester, role (primary/guest), rating

:TeachingAssignment a owl:Class ;
    rdfs:subClassOf :Event ;
    rdfs:comment "An assignment of a professor to teach a specific course" .

:hasInstructor a owl:ObjectProperty ;
    rdfs:domain :TeachingAssignment ;
    rdfs:range :Professor .

:hasCourse a owl:ObjectProperty ;
    rdfs:domain :TeachingAssignment ;
    rdfs:range :Course .

:semester a owl:DatatypeProperty ;
    rdfs:domain :TeachingAssignment ;
    rdfs:range xsd:string .
```

**When to apply:** When a binary property needs temporal scope, provenance, qualifiers, or involves >2 participants.

**Key decision:** What superclass for the reification class? Event (if temporal), or a domain-specific parent.

---

### P.06 — Participation (Entity-Event)

**Problem:** Events and their participants modeled without clear linking properties.

**Diagnostics:** S05/S08 (property deserts around event classes), coverage gaps

**Template:**
```turtle
:Event a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A discrete occurrence" .

:involves a owl:ObjectProperty ;
    rdfs:domain :Event ;
    rdfs:range :Agent ;
    rdfs:comment "An agent involved in this event" .

:occurredAt a owl:ObjectProperty ;
    rdfs:domain :Event ;
    rdfs:range :Location .

:startTime a owl:DatatypeProperty ;
    rdfs:domain :Event ;
    rdfs:range xsd:dateTime .
```

**Key decision:** Use specific participation roles (hasPerformer, hasPatient, hasInstrument) rather than generic "involves" when the domain warrants distinct roles.

---

### P.07 — Value Partition (Approximate)

**Problem:** A set of mutually exclusive values modeled as subclasses when they should be an enumeration, or vice versa.

**Diagnostics:** M03, CC03

**Template:**
```turtle
:Size a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "Mutually exclusive size categories" .

:Small a owl:Class ;
    rdfs:subClassOf :Size .

:Medium a owl:Class ;
    rdfs:subClassOf :Size .

:Large a owl:Class ;
    rdfs:subClassOf :Size .

:hasSize a owl:ObjectProperty ;
    rdfs:domain :Product ;
    rdfs:range :Size .
```

**Model limitation:** The full Value Partition pattern uses owl:oneOf + disjointness to enforce mutual exclusivity. With the current model, the subclass approximation works but lacks enforcement. Document the intent in the parent class description: "Mutually exclusive categories."

**Key decision:** Does this value set warrant classes, or should it be a datatype property? Classes when values might gain properties (Size → dimensional ranges). Datatype when they're truly just labels.

---

### P.08 — Cross-Cutting Concern Separation

**Problem:** Orthogonal classification axes baked into class names. "ActivePremiumSubscription" encodes both status and tier.

**Diagnostics:** CC01–CC04, T11

**Template:**
```turtle
# Instead of: ActiveSubscription, CancelledSubscription, PremiumSubscription

:Subscription a owl:Class ;
    rdfs:comment "A customer's subscription to a service" .

:SubscriptionStatus a owl:Class ;
    rdfs:comment "Mutually exclusive subscription lifecycle states" .

:Active a owl:Class ;
    rdfs:subClassOf :SubscriptionStatus .

:Cancelled a owl:Class ;
    rdfs:subClassOf :SubscriptionStatus .

:hasStatus a owl:ObjectProperty ;
    rdfs:domain :Subscription ;
    rdfs:range :SubscriptionStatus .

:SubscriptionTier a owl:Class ;
    rdfs:comment "Mutually exclusive subscription service levels" .

:Premium a owl:Class ;
    rdfs:subClassOf :SubscriptionTier .

:Basic a owl:Class ;
    rdfs:subClassOf :SubscriptionTier .

:hasTier a owl:ObjectProperty ;
    rdfs:domain :Subscription ;
    rdfs:range :SubscriptionTier .
```

**Principle:** Each independent classification axis gets its own class hierarchy + linking property. Combinatorial explosion of subclasses is replaced by composition.

**Note:** This pattern replaces multiple inheritance for cross-cutting concerns. Instead of a class inheriting from two axes, it links to both via properties.

---

## Pattern Selection Guide

| Symptom | Pattern |
|---|---|
| "X subClassOf Y" but X is a role Y can play | P.01 Role Separation |
| "X subClassOf Y" but X is a part of Y | P.02 Part-Whole |
| "X subClassOf Y" but X is made of Y | P.03 Constitution |
| Proper nouns or specific entities as classes | P.04 Classification |
| Binary property needs context or qualifiers | P.05 N-ary Relation |
| Event classes with no participant links | P.06 Participation |
| 3–10 leaf subclasses, all without unique properties | P.07 Value Partition |
| Class names encoding multiple independent axes | P.08 Cross-Cutting Separation |

---

## Patterns Not Applicable (Current Model)

These standard ODPs require OWL features not in the current model. Listed for reference — they become applicable as the model gains expressivity (see [FUTURE.md](FUTURE.md)).

| Pattern | Requires | Notes |
|---|---|---|
| Rector Normalization | Defined classes, multiple inheritance | Single primitive axis + defined classes with multiple parents |
| Closure Axiom | Universal restrictions | allValuesFrom to close the open-world assumption |
| SEP (Structured Ecological Profiles) | Restrictions | Multiple-criteria classification |
| Object Property Chain | Property chains | Compositional property inference |

---

## Sources

- [Ontology Design Patterns (ontologydesignpatterns.org)](http://ontologydesignpatterns.org/)
- Gangemi, A. "Ontology Design Patterns for Semantic Web Content" (ISWC 2005)
- Rector et al. "OWL Pizzas: Practical Experience of Teaching OWL-DL" (EKAW 2004)
- Presutti et al. "Content Ontology Design Patterns as Practical Building Blocks for Web Ontologies" (ER 2009)
