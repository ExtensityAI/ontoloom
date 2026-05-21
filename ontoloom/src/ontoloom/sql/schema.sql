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
-- Covering probe for MentionsAll's EXISTS chains: lets each per-IRI EXISTS hit
-- (axiom_id=? AND entity_iri=?) without re-filtering after an axiom_id scan.
CREATE INDEX IF NOT EXISTS idx_axiom_entities_axiom_iri ON axiom_entities(axiom_id, entity_iri);
-- Role-leading index so `count_entities_by_role` GROUP BY walks in role-grouped
-- order and skips the TEMP B-TREE. Partial (role IS NOT NULL) keeps the index
-- small; the predicate matches every consumer of this index.
CREATE INDEX IF NOT EXISTS idx_axiom_entities_role_iri
    ON axiom_entities(role, entity_iri) WHERE role IS NOT NULL;

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
CREATE INDEX IF NOT EXISTS idx_axiom_text_lower_text
    ON axiom_text(LOWER(text));
CREATE INDEX IF NOT EXISTS idx_axiom_text_prop_lower_text
    ON axiom_text(property, LOWER(text));

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

-- `id` is an INTEGER PRIMARY KEY (rowid alias) so we can index `(selection_name, id)`
-- and serve paginated `ORDER BY id` reads without a temp B-tree sort.
CREATE TABLE IF NOT EXISTS selection_items (
    id INTEGER PRIMARY KEY,
    selection_name TEXT NOT NULL REFERENCES selections(name) ON DELETE CASCADE,
    item TEXT NOT NULL,
    UNIQUE(selection_name, item)
);

CREATE INDEX IF NOT EXISTS idx_selection_items_name_id
    ON selection_items(selection_name, id);
