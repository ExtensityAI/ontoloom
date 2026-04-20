-- Single-row key/value store for ontology-wide metadata (currently just prefixes).
CREATE TABLE IF NOT EXISTS metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);

-- Canonical axiom store. `hash` is a canonical hash of the axiom content and
-- acts as the dedup key (INSERT OR IGNORE on add). `data` is JSONB so we can
-- round-trip full Pydantic models without a relational schema per axiom type.
-- `source` distinguishes user-asserted axioms from reasoner-inferred ones.
CREATE TABLE IF NOT EXISTS axioms (
    id INTEGER PRIMARY KEY,
    hash TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    data BLOB NOT NULL,
    source TEXT NOT NULL DEFAULT 'asserted' CHECK (source IN ('asserted', 'inferred'))
);

CREATE INDEX IF NOT EXISTS idx_axioms_type ON axioms(type);

-- Derived index: every entity IRI referenced by an axiom, with its structural
-- role (Class, ObjectProperty, ...) when known. Enables entity lookup and
-- role/namespace filtering without scanning axiom JSON. Repopulated from
-- `axioms.data` on insert; cascades on delete.
CREATE TABLE IF NOT EXISTS axiom_entities (
    axiom_id INTEGER NOT NULL REFERENCES axioms(id) ON DELETE CASCADE,
    entity_iri TEXT NOT NULL,
    role TEXT
);

CREATE INDEX IF NOT EXISTS idx_axiom_entities_iri ON axiom_entities(entity_iri);
CREATE INDEX IF NOT EXISTS idx_axiom_entities_iri_role ON axiom_entities(entity_iri, role);
CREATE INDEX IF NOT EXISTS idx_axiom_entities_axiom ON axiom_entities(axiom_id);

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

-- Append-only event log of add/del operations, tagged by session. `axiom_json`
-- is captured on 'add' (as JSONB) so events are self-contained for replay even
-- after the axiom is deleted; 'del' events only need the hash.
CREATE TABLE IF NOT EXISTS events (
    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    op TEXT NOT NULL CHECK (op IN ('add', 'del')),
    axiom_hash TEXT NOT NULL,
    axiom_json BLOB,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);
