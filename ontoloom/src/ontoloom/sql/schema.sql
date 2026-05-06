-- Single-row key/value store for ontology-wide metadata (currently just prefixes).
CREATE TABLE IF NOT EXISTS metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);

-- Canonical axiom store. `hash` is a canonical hash of the axiom content and
-- acts as the dedup key (INSERT OR IGNORE on add). `data` is JSONB so we can
-- round-trip full Pydantic models without a relational schema per axiom type.
CREATE TABLE IF NOT EXISTS axioms (
    id INTEGER PRIMARY KEY,
    hash TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    data BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_axioms_type ON axioms(type);

-- Derived index: every entity IRI referenced by an axiom, with its structural
-- role (Class, ObjectProperty, ...) when known. Enables entity lookup and
-- role/namespace filtering without scanning axiom JSON. Repopulated from
-- `axioms.data` on insert; cascades on delete.
CREATE TABLE IF NOT EXISTS axiom_entities (
    axiom_id INTEGER NOT NULL REFERENCES axioms(id) ON DELETE CASCADE,
    entity_iri TEXT NOT NULL,
    role TEXT,
    position TEXT
);

CREATE INDEX IF NOT EXISTS idx_axiom_entities_iri ON axiom_entities(entity_iri);
CREATE INDEX IF NOT EXISTS idx_axiom_entities_iri_role ON axiom_entities(entity_iri, role);
CREATE INDEX IF NOT EXISTS idx_axiom_entities_axiom ON axiom_entities(axiom_id);
CREATE INDEX IF NOT EXISTS idx_axiom_entities_iri_pos ON axiom_entities(entity_iri, position, axiom_id);
CREATE INDEX IF NOT EXISTS idx_axiom_entities_axiom_pos ON axiom_entities(axiom_id, position);

-- Derived text index keyed to a specific entity: the entity's local_name plus
-- any AnnotationAssertion values targeting it (labels, comments, ...). Used
-- for entity text search; `property` discriminates local_name from annotations.
CREATE TABLE IF NOT EXISTS entity_text (
    axiom_id INTEGER NOT NULL REFERENCES axioms(id) ON DELETE CASCADE,
    entity_iri TEXT NOT NULL,
    text TEXT NOT NULL,
    property TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entity_text_iri ON entity_text(entity_iri);
CREATE INDEX IF NOT EXISTS idx_entity_text_prop_text ON entity_text(property, text);
CREATE INDEX IF NOT EXISTS idx_entity_text_axiom ON entity_text(axiom_id);
CREATE INDEX IF NOT EXISTS idx_entity_text_covering ON entity_text(entity_iri, property, text);

-- Derived text index for axiom-level metadata annotations (annotations *on*
-- the axiom itself, not on an entity). Kept separate from entity_text because
-- these have no subject entity to key on. Used by axiom annotation search.
CREATE TABLE IF NOT EXISTS axiom_text (
    axiom_id INTEGER NOT NULL REFERENCES axioms(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    property TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_axiom_text_axiom ON axiom_text(axiom_id);
CREATE INDEX IF NOT EXISTS idx_axiom_text_text ON axiom_text(text);
CREATE INDEX IF NOT EXISTS idx_axiom_text_property ON axiom_text(property);

-- Append-only event log of all mutations, tagged by session. `axiom_json`
-- is stored on add, del, and replace so events are self-contained for revert.
-- `replaces_hash` links replace events to the axiom they replaced.
-- `annotation_diff` stores JSON diff for annotate events.
-- `batch_id` groups related events (e.g., rename_iri) for atomic revert.
CREATE TABLE IF NOT EXISTS events (
    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    op TEXT NOT NULL CHECK (op IN ('add', 'del', 'replace', 'annotate')),
    axiom_hash TEXT NOT NULL,
    axiom_json BLOB,
    replaces_hash TEXT,
    annotation_diff TEXT,
    batch_id TEXT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Named selections: persistent sets of axiom hashes or entity IRIs.
-- Kind is inferred from the producing operation. Content hash enables
-- optimistic locking (write ops require name@hash_prefix).
CREATE TABLE IF NOT EXISTS selections (
    name TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('axioms', 'entities')),
    hash TEXT NOT NULL,
    size INTEGER NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS selection_items (
    selection_name TEXT NOT NULL REFERENCES selections(name) ON DELETE CASCADE,
    item TEXT NOT NULL,
    UNIQUE(selection_name, item)
);

-- UNIQUE(selection_name, item) already provides a covering index for name-based lookups.
CREATE INDEX IF NOT EXISTS idx_selection_items_item ON selection_items(item);
