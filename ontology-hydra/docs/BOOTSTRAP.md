# Bootstrap Phase

The bootstrap phase is the structured first phase before the main diagnose/resolve loop. It captures the user's intent, establishes scope, and produces the initial ontology seed.

For overall lifecycle, see [ARCHITECTURE.md](ARCHITECTURE.md) § Lifecycle. For the prompt template used during bootstrap, see [PROMPTING.md](PROMPTING.md) § Bootstrap Turn.

---

## Purpose

The bootstrap captures initial direction so the system can begin generating. The user is NOT expected to know everything upfront — the scope document grows organically as the system encounters ambiguity during the main loop.

### What Bootstrap Requires

1. **User intent** — what the ontology is for, what domain, what purpose. The intent informs the abstraction level: what belongs in the ontology (classes, properties, structure) vs. what belongs in a knowledge graph (instances, facts, data).
2. **Domain documents** (required) — source material about the domain. Database schemas, requirements docs, sample records, API specs, textbook chapters, spreadsheets, etc. These ground the system in real domain content rather than LLM training data.

### What Bootstrap Produces

1. **Scope document** — the drift anchor, now grounded in real documents (see § Scope Document below)
2. **Document index** — summaries of all provided documents, used throughout the main loop (see § Document Index below)
3. **Initial ontology** — a minimal seed grounded in the documents, not a comprehensive draft
4. **User alignment** — the system and user have a shared understanding of what's being built

---

## Bootstrap Flow

### Step 1: Build Document Index

The system processes all provided documents into a document index. Each document gets a short summary (~50–100 tokens) capturing what domain concepts, relationships, and constraints it describes.

```
[1] patient_admission_protocol.pdf — "Describes the admission workflow:
    triage, attending physician assignment, initial lab orders, diagnosis..."
[2] lab_test_catalog.xlsx — "List of 340 lab tests with categories,
    normal ranges, turnaround times, specimen types..."
[3] department_org_chart.pdf — "Hospital organizational structure:
    departments, divisions, roles, reporting lines..."
[4] ehr_schema.sql — "Database schema for electronic health records:
    patients, encounters, orders, results, medications..."
```

The document index persists throughout the session and is available to all agents via search tools. See [EXPLORATION.md](EXPLORATION.md) § Document Tools.

### Step 2: Understand Intent and Documents

The system reads the user's intent and the document index (plus selected high-priority full documents) to understand the domain:

- What domain is this?
- What are the major concept areas visible in the documents?
- What abstraction level does the intent imply? (What belongs in the ontology vs. in a knowledge graph built from this ontology?)
- What's the likely purpose (querying, classification, data integration)?

The intent informs *how to interpret* the documents. The same database schema produces different ontologies depending on whether the intent is "model hospital operations" (operational ontology) vs. "model medical knowledge" (domain ontology).

### Step 3: Ask Scoping Questions

2–3 questions grounded in what the documents contain:

- **What to represent** — "Your documents describe patients, physicians, lab tests, diagnoses, and treatment plans. Should the ontology cover all of these, or focus on a subset?"
- **What to answer** — what queries should the ontology support? (Soft guidance, not a hard spec.)
- **What's out of scope** — "The documents also mention billing codes and insurance providers. Should the ontology include these?"

Questions are framed in plain language, grounded in concrete document content rather than abstract domain concepts. The user is not an ontology engineer. No OWL jargon.

**Good:** "Your org chart shows physicians with specialties. Should the ontology track specialties, or just model physicians as a single category?"
**Bad:** "Should we model hasSpecialty as a functional object property with domain Physician?"

### Step 4: Seed the Scope Document

The system creates the scope document from what it learned — the user's goals, document-derived domain understanding, initial include/exclude decisions, and any design principles that emerged.

### Step 5: Generate Initial Ontology

Using its ontology modeling expertise, the provided documents, and established ontology design patterns (see [PATTERNS.md](PATTERNS.md)), the system generates an initial seed covering the major concept areas. The seed is:

- **Minimal** — just enough structure to start the diagnostic loop
- **Grounded in documents** — reflects actual domain content, not generic LLM patterns
- **Informed by intent** — abstraction level matches the stated purpose
- **Imperfect on purpose** — the diagnostic loop will refine it

The ontology starts from `Thing` and builds top-level classes with initial properties. The first diagnostic round will identify everything that's wrong or missing.

#### Rigidity Backbone

The seed prioritizes **rigid natural kinds** as the structural backbone — concepts whose instances cannot lose membership without ceasing to exist (Person, Vehicle, Location, Organization). Anti-rigid concepts (Student, Driver, Manager — roles that an entity can enter and leave) are layered on top using the Role Separation pattern (P.01), not as subclasses.

This matters because rigid classes form the stable foundation that downstream phases build on. Getting the backbone right means Phase 1 and Phase 2 fixes are less likely to require costly structural reversals. Anti-rigid concepts modeled as subclasses are the single most common source of taxonomy rework.

See [PATTERNS.md](PATTERNS.md) § Rigidity Backbone for the OntoClean metaproperties that inform this distinction.

---

## Scope Document

The scope document is the system's drift anchor — the accumulated understanding of what's in scope, what's out, and why. It persists across all diagnostic rounds.

### Format

```markdown
## User Goals
- [Original user request — never modified]

## Decided Scope
### [Domain Area]
- Include: ...
- Exclude: ... (user decision, round N)
- Granularity: ...

### [Domain Area]
- [pending user decision on ...]

## Design Principles
- [Principle] (source: user/system, round N)
```

### Rules

- The scope document is **never summarized or compacted.** Always included in full.
- Each entry records **provenance** — which round, user or system decision.
- Soft guidance, not hard boundaries. The system can deviate if it explains why.
- The user can correct it at any time.
- Grows organically as the system encounters ambiguity.

---

## Document Index

The document index maps every user-provided document to a short summary. It serves as a navigational tool — agents search it to find relevant documents and read them in full when needed.

### Format

```
[doc_id] filename — "summary of contents (~50-100 tokens)"
```

### Rules

- Every provided document gets an entry. No documents are silently ignored.
- Summaries capture domain concepts, relationships, and constraints present in the document — not just the document type.
- The index is created once during bootstrap and does not change (documents are not added mid-session).
- The index is available to all agents (bootstrap, exploration, resolution) via `search_documents()`.
- Full document content is accessed via `research_document(doc_id, question)` — a document research subagent reads the document and returns a concise, cached answer. See [EXPLORATION.md](EXPLORATION.md) § Document Research Subagent.
- The document index is always built in full, regardless of document count — each summary is a small LLM call, parallelizable.
- During bootstrap, the system selects 3–5 high-priority documents for full reads based on intent relevance and information density (e.g., database schemas and structured specs over narrative prose). This selection is automated — the system triages, not the user.
- The research subagent pattern (see [EXPLORATION.md](EXPLORATION.md) § Document Research Subagent) handles all other document access on-demand during the main loop.

---

### Scope Echo

The scope document sits at the top of prompt context (primacy bias). The prompt instructions additionally echo the 2–3 most important scope constraints at the bottom (recency bias). This double-anchoring — top and bottom — is the strongest anti-drift measure available.

The echo is extracted automatically: pick the top entries from "Decided Scope" (exclude/include decisions) and "Design Principles." Keep it under ~50 tokens.

Based on research: simple reminder interventions reliably reduce goal divergence ("Drift No More," Oct 2025).

---

## User Interaction

### When to Ask the User

The system surfaces questions when it encounters genuine modeling ambiguity that depends on the user's domain knowledge or preferences:

- **Scope boundaries** — "The ontology includes Aircraft. Should it also cover ground support equipment (fuel trucks, baggage carts)?"
- **Modeling philosophy** — "Employees can be managers. Should Manager be a separate class, or a role that any Employee can have?"
- **Granularity** — "How detailed should the sensor hierarchy be? Just sensor types (temperature, pressure), or also specific models?"

### How to Frame Questions

Questions must be understandable by someone who knows the domain but not OWL:

| Concept | Plain language | Not this |
|---|---|---|
| subClassOf vs. role | "Should X be a type of Y, or a role that Y can have?" | "Should X be modeled as anti-rigid per OntoClean?" |
| partOf vs. is-a | "Is X a component of Y, or a kind of Y?" | "Should we use mereological vs. taxonomic relations?" |
| Granularity | "How detailed should this area be?" | "What's the target depth for this subtree?" |
| Scope | "Should the ontology include X?" | "Should we expand the domain closure to include X?" |

### Non-Blocking Questions

In interactive mode, questions don't block the system. The system continues working on other areas and incorporates answers when they arrive. This prevents the system from stalling while waiting for user input.

---

## Stopping Conditions

See [ARCHITECTURE.md](ARCHITECTURE.md) § Stopping for the full stopping criteria. The conditions include phase completion, document coverage, deferred decision review, and a final self-review with full-depth exploration.

---

## Example Bootstrap

**User intent:** "An ontology for a university course management system"

**User documents:**
- `course_catalog.pdf` — "Fall 2025 course catalog: 450 courses across 32 departments with prerequisites, credit hours, instructor assignments"
- `student_records_schema.sql` — "Database schema: students, enrollments, grades, academic_programs, advisors, degree_requirements"
- `room_booking_system_api.json` — "API spec for room reservations: rooms, buildings, time_slots, capacities, equipment"
- `faculty_handbook.pdf` — "Faculty policies: tenure tracks, teaching loads, committee assignments, sabbaticals, adjunct vs. full-time"

**Document index built.** System reads document summaries + full `student_records_schema.sql` (most structured, high information density).

**System reflection:**
"This is an academic/education domain. Your documents describe: people in multiple roles (students, faculty with tenure tracks, advisors), courses with prerequisite chains and credit structures, facilities with room booking, and organizational structure (departments, programs). The database schema suggests the purpose is operational data integration."

**Scoping questions:**
1. "Your documents cover courses, rooms, and scheduling. Should the ontology model all of these, or focus on the academic structure (courses, programs, people) without facilities?"
2. "The faculty handbook describes tenure tracks, committee assignments, and sabbaticals. Your student records have advisors and degree requirements. How detailed should the people modeling be — just roles (student, faculty), or also these career/academic structures?"
3. "The database schema shows grades and degree requirements. Should the ontology model the assessment/evaluation side, or just the structural relationships (who teaches what, who enrolls where)?"

**Initial scope document:**
```markdown
## User Goals
- An ontology for a university course management system

## Documents
- course_catalog.pdf, student_records_schema.sql, room_booking_system_api.json, faculty_handbook.pdf

## Decided Scope
### People
- Include: students, faculty, staff (from student_records_schema + faculty_handbook)
- [pending: role modeling depth — waiting for user answer on Q2]

### Courses
- Include: courses, programs, departments, prerequisites (from course_catalog + student_records_schema)
- Granularity: course level (not individual lectures/sessions)

### Facilities & Scheduling
- [pending user decision on Q1]

### Assessment
- [pending user decision on Q3]

## Design Principles
- (none yet)
```

**Initial ontology seed:** Top-level classes for Person, Course, Department, Program with basic properties drawn from the database schema. The diagnostic loop will check the ontology against the full document set for coverage gaps and drive expansion.
