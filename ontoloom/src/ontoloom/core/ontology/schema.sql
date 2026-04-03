CREATE TABLE IF NOT EXISTS metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS axioms (
    id INTEGER PRIMARY KEY,
    hash TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    data BLOB NOT NULL,
    source TEXT NOT NULL DEFAULT 'asserted' CHECK (source IN ('asserted', 'inferred'))
);

CREATE TABLE IF NOT EXISTS axiom_entities (
    axiom_id INTEGER NOT NULL REFERENCES axioms(id) ON DELETE CASCADE,
    entity_iri TEXT NOT NULL,
    role TEXT
);

CREATE INDEX IF NOT EXISTS idx_axiom_entities_iri ON axiom_entities(entity_iri);
CREATE INDEX IF NOT EXISTS idx_axiom_entities_axiom ON axiom_entities(axiom_id);

CREATE TABLE IF NOT EXISTS entity_text (
    axiom_id INTEGER NOT NULL REFERENCES axioms(id) ON DELETE CASCADE,
    entity_iri TEXT NOT NULL,
    text TEXT NOT NULL,
    property TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entity_text_iri ON entity_text(entity_iri);
CREATE INDEX IF NOT EXISTS idx_entity_text_text ON entity_text(text);
CREATE INDEX IF NOT EXISTS idx_entity_text_axiom ON entity_text(axiom_id);

CREATE TABLE IF NOT EXISTS axiom_text (
    axiom_id INTEGER NOT NULL REFERENCES axioms(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    property TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_axiom_text_axiom ON axiom_text(axiom_id);
CREATE INDEX IF NOT EXISTS idx_axiom_text_text ON axiom_text(text);

CREATE TABLE IF NOT EXISTS events (
    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    op TEXT NOT NULL CHECK (op IN ('add', 'del')),
    axiom_hash TEXT NOT NULL,
    axiom_json BLOB,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);
