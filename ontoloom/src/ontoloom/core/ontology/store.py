"""SQLite-based ontology storage with derived index tables."""

from __future__ import annotations

import hashlib
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from ontoloom.core.ontology.extract import extract_from_axiom
from ontoloom.core.ontology.models.axioms import AnnotationAssertion, Axiom
from ontoloom.core.ontology.models.base import EntityType
from ontoloom.core.ontology.models.literals import IRI, LangLiteral, TypedLiteral

_SCHEMA = """\
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

CREATE TABLE IF NOT EXISTS axiom_iris (
    iri TEXT NOT NULL,
    role TEXT,
    axiom_id INTEGER NOT NULL REFERENCES axioms(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_axiom_iris_iri ON axiom_iris(iri);
CREATE INDEX IF NOT EXISTS idx_axiom_iris_axiom ON axiom_iris(axiom_id);

CREATE TABLE IF NOT EXISTS entity_names (
    iri TEXT NOT NULL,
    name TEXT NOT NULL,
    source TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entity_names_iri ON entity_names(iri);
CREATE INDEX IF NOT EXISTS idx_entity_names_name ON entity_names(name);

CREATE TABLE IF NOT EXISTS axiom_annotations (
    axiom_id INTEGER NOT NULL REFERENCES axioms(id) ON DELETE CASCADE,
    property TEXT NOT NULL,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_axiom_annotations_axiom ON axiom_annotations(axiom_id);
CREATE INDEX IF NOT EXISTS idx_axiom_annotations_value ON axiom_annotations(value);
"""

_PRAGMAS = """\
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
"""


# =============================================================================
# Data types
# =============================================================================


@dataclass
class AnnotationRow:
    property: IRI
    value: str


@dataclass
class EntityInfo:
    roles: set[EntityType]
    annotations: list[AnnotationRow]
    axiom_counts: Counter[str]


@dataclass
class EntityMatch:
    iri: IRI
    roles: set[EntityType]
    annotations: list[AnnotationRow]
    match_source: str
    match_quality: str


@dataclass
class HashedAxiom:
    axiom: Axiom
    hash: str


@dataclass
class SearchPage:
    axioms: list[HashedAxiom]
    total: int


@dataclass
class AddResult:
    added: list[HashedAxiom]
    skipped: list[HashedAxiom]


@dataclass
class RemoveResult:
    removed: list[HashedAxiom]


# =============================================================================
# Helpers
# =============================================================================


def _hash_axiom(axiom: Axiom) -> str:
    return hashlib.sha256(axiom.model_dump_json().encode()).hexdigest()


def _extract_annotation_value(value: IRI | TypedLiteral | LangLiteral) -> str:
    if isinstance(value, IRI):
        return str(value)
    return value.value


_AXIOM_ADAPTER = None


def _get_axiom_adapter():
    global _AXIOM_ADAPTER
    if _AXIOM_ADAPTER is None:
        from pydantic import TypeAdapter

        _AXIOM_ADAPTER = TypeAdapter(Axiom)
    return _AXIOM_ADAPTER


# =============================================================================
# Store
# =============================================================================


class OntologyStore:
    """SQLite-based ontology storage."""

    @classmethod
    def create(cls, path: Path) -> Self:
        if path.exists():
            msg = f"'{path}' already exists."
            raise FileExistsError(msg)
        conn = sqlite3.connect(str(path))
        conn.executescript(_PRAGMAS)
        conn.executescript(_SCHEMA)
        conn.execute("INSERT INTO metadata (id, data) VALUES (1, ?)", ('{"prefixes": []}',))
        conn.commit()
        conn.close()
        return cls(path)

    def __init__(self, path: Path):
        if not path.exists():
            msg = f"'{path}' does not exist. Create it first with OntologyStore.create()."
            raise FileNotFoundError(msg)
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_PRAGMAS)

    def close(self):
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # -- Axiom operations --

    def add_axioms(self, axioms: list[Axiom]) -> AddResult:
        added: list[HashedAxiom] = []
        skipped: list[HashedAxiom] = []
        cur = self._conn.cursor()

        try:
            for axiom in axioms:
                h = _hash_axiom(axiom)
                json_data = axiom.model_dump_json()
                cur.execute(
                    "INSERT OR IGNORE INTO axioms (hash, type, data) VALUES (?, ?, jsonb(?))",
                    (h, axiom.type, json_data),
                )
                ha = HashedAxiom(axiom=axiom, hash=h)

                if cur.rowcount == 0:
                    skipped.append(ha)
                    continue

                added.append(ha)
                axiom_id = cur.lastrowid

                # Populate axiom_iris + entity_names for IRI local names
                seen_iris: set[str] = set()
                for iri, role in extract_from_axiom(axiom):
                    iri_str = str(iri)
                    role_val = role.value if isinstance(role, EntityType) else role
                    cur.execute(
                        "INSERT INTO axiom_iris (iri, role, axiom_id) VALUES (?, ?, ?)",
                        (iri_str, role_val, axiom_id),
                    )
                    # Add IRI local name to entity_names (once per IRI per axiom)
                    if iri_str not in seen_iris:
                        seen_iris.add(iri_str)
                        cur.execute(
                            "INSERT INTO entity_names (iri, name, source) VALUES (?, ?, 'local_name')",
                            (iri_str, iri.local_name),
                        )

                # Populate entity_names for AnnotationAssertion values
                if isinstance(axiom, AnnotationAssertion):
                    cur.execute(
                        "INSERT INTO entity_names (iri, name, source) VALUES (?, ?, ?)",
                        (
                            str(axiom.subject),
                            _extract_annotation_value(axiom.value),
                            str(axiom.property),
                        ),
                    )

                # Populate axiom_annotations for axiom-level annotations
                for ann in axiom.annotations:
                    cur.execute(
                        "INSERT INTO axiom_annotations (axiom_id, property, value) VALUES (?, ?, ?)",
                        (axiom_id, str(ann.property), _extract_annotation_value(ann.value)),
                    )

            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        return AddResult(added=added, skipped=skipped)

    def remove_by_hash_prefix(self, prefixes: list[str]) -> RemoveResult:
        cur = self._conn.cursor()
        to_remove: list[HashedAxiom] = []

        try:
            for prefix in prefixes:
                cur.execute(
                    "SELECT id, hash, json(data) FROM axioms WHERE hash GLOB ? || '*'",
                    (prefix,),
                )
                rows = cur.fetchall()

                if not rows:
                    msg = f"[{prefix}] not found"
                    raise ValueError(msg)
                if len(rows) > 1:
                    matches = ", ".join(r[1][:8] for r in rows)
                    msg = f"[{prefix}] matches {len(rows)} axioms: {matches}"
                    raise ValueError(msg)

                _, full_hash, json_data = rows[0]
                axiom = _get_axiom_adapter().validate_json(json_data)
                to_remove.append(HashedAxiom(axiom=axiom, hash=full_hash))

            for ha in to_remove:
                # Delete axiom (CASCADE handles axiom_iris + axiom_annotations)
                cur.execute("DELETE FROM axioms WHERE hash = ?", (ha.hash,))
                # Clean up entity_names for this axiom's IRIs
                # (entity_names doesn't have axiom_id FK, so we clean manually)
                for iri, _ in extract_from_axiom(ha.axiom):
                    cur.execute(
                        "DELETE FROM entity_names WHERE iri = ? AND source = 'local_name'",
                        (str(iri),),
                    )
                if isinstance(ha.axiom, AnnotationAssertion):
                    cur.execute(
                        "DELETE FROM entity_names WHERE iri = ? AND source = ? AND name = ?",
                        (
                            str(ha.axiom.subject),
                            str(ha.axiom.property),
                            _extract_annotation_value(ha.axiom.value),
                        ),
                    )

            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        return RemoveResult(removed=to_remove)

    # -- Entity queries --

    def get_entity(self, iri: IRI) -> EntityInfo | None:
        cur = self._conn.cursor()
        iri_str = str(iri)

        cur.execute("SELECT 1 FROM axiom_iris WHERE iri = ? LIMIT 1", (iri_str,))
        if cur.fetchone() is None:
            return None

        # Roles
        cur.execute(
            "SELECT DISTINCT role FROM axiom_iris WHERE iri = ? AND role IS NOT NULL", (iri_str,)
        )
        roles = {EntityType(r[0]) for r in cur.fetchall()}

        # Annotations (from entity_names, excluding local_name)
        cur.execute(
            "SELECT source, name FROM entity_names WHERE iri = ? AND source != 'local_name'",
            (iri_str,),
        )
        annotations = [AnnotationRow(property=IRI(r[0]), value=r[1]) for r in cur.fetchall()]

        # Axiom counts (non-annotation)
        cur.execute(
            """
            SELECT a.type, COUNT(DISTINCT a.id)
            FROM axiom_iris i
            JOIN axioms a ON i.axiom_id = a.id
            WHERE i.iri = ? AND a.type != 'AnnotationAssertion'
            GROUP BY a.type
            """,
            (iri_str,),
        )
        axiom_counts = Counter({r[0]: r[1] for r in cur.fetchall()})

        return EntityInfo(roles=roles, annotations=annotations, axiom_counts=axiom_counts)

    # -- Search --

    def search_entities(
        self,
        query: str,
        scope: Literal["iri", "annotations", "all"] = "all",
        limit: int = 50,
    ) -> list[EntityMatch]:
        matches: dict[str, tuple[str, str]] = {}

        if scope in ("iri", "all"):
            self._find_name_matches(query, "local_name", "iri", matches, limit)

        if scope in ("annotations", "all"):
            self._find_annotation_name_matches(query, matches, limit)

        if not matches:
            return []

        # Batch-fetch roles and display annotations for all matching IRIs
        cur = self._conn.cursor()
        iri_list = list(matches.keys())
        placeholders = ",".join("?" for _ in iri_list)

        cur.execute(
            f"SELECT iri, role FROM axiom_iris WHERE iri IN ({placeholders}) AND role IS NOT NULL",
            iri_list,
        )
        roles_by_iri: dict[str, set[EntityType]] = {}
        for iri_str, role in cur.fetchall():
            roles_by_iri.setdefault(iri_str, set()).add(EntityType(role))

        cur.execute(
            f"SELECT iri, source, name FROM entity_names WHERE iri IN ({placeholders}) AND source != 'local_name'",
            iri_list,
        )
        anns_by_iri: dict[str, list[AnnotationRow]] = {}
        for iri_str, source, name in cur.fetchall():
            anns_by_iri.setdefault(iri_str, []).append(
                AnnotationRow(property=IRI(source), value=name)
            )

        results = [
            EntityMatch(
                iri=IRI(iri_str),
                roles=roles_by_iri.get(iri_str, set()),
                annotations=anns_by_iri.get(iri_str, []),
                match_source=source,
                match_quality=quality,
            )
            for iri_str, (source, quality) in matches.items()
        ]

        results.sort(
            key=lambda m: (
                0 if m.match_quality == "exact" else 1,
                0 if m.match_source == "iri" else 1,
            ),
        )
        return results[:limit]

    def _find_name_matches(
        self,
        query: str,
        source_filter: str,
        match_source: str,
        matches: dict[str, tuple[str, str]],
        limit: int,
    ):
        cur = self._conn.cursor()

        # Exact match
        cur.execute(
            "SELECT DISTINCT iri FROM entity_names WHERE source = ? AND name = ? LIMIT ?",
            (source_filter, query, limit),
        )
        for (iri_str,) in cur.fetchall():
            if iri_str not in matches:
                matches[iri_str] = (match_source, "exact")

        # Substring match
        cur.execute(
            "SELECT DISTINCT iri FROM entity_names WHERE source = ? AND name LIKE '%' || ? || '%' LIMIT ?",
            (source_filter, query, limit),
        )
        for (iri_str,) in cur.fetchall():
            if iri_str not in matches:
                matches[iri_str] = (match_source, "substring")

    def _find_annotation_name_matches(
        self, query: str, matches: dict[str, tuple[str, str]], limit: int
    ):
        cur = self._conn.cursor()

        # Exact match on annotation values (source != 'local_name')
        cur.execute(
            "SELECT DISTINCT iri FROM entity_names WHERE source != 'local_name' AND name = ? LIMIT ?",
            (query, limit),
        )
        for (iri_str,) in cur.fetchall():
            if iri_str not in matches:
                matches[iri_str] = ("annotation", "exact")

        # Substring match
        cur.execute(
            "SELECT DISTINCT iri FROM entity_names WHERE source != 'local_name' AND name LIKE '%' || ? || '%' LIMIT ?",
            (query, limit),
        )
        for (iri_str,) in cur.fetchall():
            if iri_str not in matches:
                matches[iri_str] = ("annotation", "substring")

    def search_by_iri(
        self,
        iri: IRI,
        axiom_types: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SearchPage:
        cur = self._conn.cursor()
        iri_str = str(iri)

        type_filter = ""
        params: list = [iri_str]
        if axiom_types:
            placeholders = ",".join("?" for _ in axiom_types)
            type_filter = f" AND a.type IN ({placeholders})"
            params.extend(axiom_types)

        cur.execute(
            f"SELECT COUNT(DISTINCT a.id) FROM axiom_iris i JOIN axioms a ON i.axiom_id = a.id WHERE i.iri = ?{type_filter}",
            params,
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"SELECT DISTINCT a.hash, json(a.data) FROM axiom_iris i JOIN axioms a ON i.axiom_id = a.id WHERE i.iri = ?{type_filter} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )

        adapter = _get_axiom_adapter()
        axioms = [
            HashedAxiom(axiom=adapter.validate_json(row[1]), hash=row[0]) for row in cur.fetchall()
        ]

        return SearchPage(axioms=axioms, total=total)

    def search_axiom_annotations(self, query: str, limit: int = 50, offset: int = 0) -> SearchPage:
        cur = self._conn.cursor()
        adapter = _get_axiom_adapter()

        cur.execute(
            "SELECT COUNT(DISTINCT aa.axiom_id) FROM axiom_annotations aa WHERE aa.value LIKE '%' || ? || '%'",
            (query,),
        )
        total = cur.fetchone()[0]

        cur.execute(
            """
            SELECT DISTINCT a.hash, json(a.data)
            FROM axiom_annotations aa
            JOIN axioms a ON aa.axiom_id = a.id
            WHERE aa.value LIKE '%' || ? || '%'
            LIMIT ? OFFSET ?
            """,
            (query, limit, offset),
        )
        axioms = [
            HashedAxiom(axiom=adapter.validate_json(row[1]), hash=row[0]) for row in cur.fetchall()
        ]

        return SearchPage(axioms=axioms, total=total)

    # -- Summaries --

    def axiom_summary(self) -> Counter[str]:
        cur = self._conn.cursor()
        cur.execute("SELECT type, COUNT(*) FROM axioms GROUP BY type")
        return Counter({r[0]: r[1] for r in cur.fetchall()})

    def entity_summary(self) -> tuple[int, Counter[str]]:
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT iri) FROM axiom_iris")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT role, COUNT(DISTINCT iri) FROM axiom_iris WHERE role IS NOT NULL GROUP BY role"
        )
        role_counts = Counter({r[0]: r[1] for r in cur.fetchall()})
        return total, role_counts
