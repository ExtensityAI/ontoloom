"""SQLite-based ontology storage with derived index tables and silent event log."""

from __future__ import annotations

import importlib.resources
import json
import sqlite3
import uuid
from collections import Counter
from pathlib import Path
from typing import Self

from pydantic import TypeAdapter

from ontoloom.core.ontology.canonical import content_hash
from ontoloom.core.ontology.extract import extract_from_axiom
from ontoloom.core.ontology.models.axioms import AnnotationAssertion, Axiom
from ontoloom.core.ontology.models.base import EntityType
from ontoloom.core.ontology.models.literals import (
    IRI,
    Annotation,
    LangLiteral,
    TypedLiteral,
)
from ontoloom.core.ontology.types import (
    AddResult,
    AnnotationRow,
    EntityInfo,
    EntityMatch,
    EntitySearchPage,
    HashedAxiom,
    RemoveResult,
    SearchPage,
)

_SQL_DIR = importlib.resources.files("ontoloom.core.ontology")
_SCHEMA = _SQL_DIR.joinpath("schema.sql").read_text()
_PRAGMAS = _SQL_DIR.joinpath("pragmas.sql").read_text()
_AXIOM_ADAPTER: TypeAdapter[Axiom] = TypeAdapter(Axiom)


def _extract_annotation_value(value: IRI | TypedLiteral | LangLiteral) -> str:
    if isinstance(value, IRI):
        return str(value)
    return value.value


class StoreNotOpenError(RuntimeError):
    """Raised when store methods are called outside a ``with`` block."""


class OntologyStore:
    """SQLite-based ontology storage. Must be used as a context manager."""

    @classmethod
    def create(cls, path: Path) -> Self:
        if path.exists():
            msg = f"'{path}' already exists."
            raise FileExistsError(msg)
        conn = sqlite3.connect(str(path), autocommit=True)
        conn.executescript(_PRAGMAS)
        conn.executescript(_SCHEMA)
        conn.execute("INSERT INTO metadata (id, data) VALUES (1, ?)", ('{"prefixes": {}}',))
        conn.close()
        return cls(path)

    def __init__(self, path: Path, *, session_id: str | None = None):
        if not path.exists():
            msg = f"'{path}' does not exist. Create it first with OntologyStore.create()."
            raise FileNotFoundError(msg)
        self._path = path
        self._session_id = session_id or uuid.uuid4().hex
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            msg = "Store is not open. Use `with OntologyStore(path) as store:`."
            raise StoreNotOpenError(msg)
        return self._conn

    def __enter__(self) -> Self:
        self._conn = sqlite3.connect(str(self._path), autocommit=False)
        # PRAGMAs must be set outside a transaction; use autocommit temporarily
        self._conn.autocommit = True
        for line in _PRAGMAS.strip().splitlines():
            line = line.strip()
            if line:
                self._conn.execute(line)
        self._conn.autocommit = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- Event log --

    def _log_event(self, op: str, axiom_hash: str, axiom_json: str | None = None) -> None:
        if axiom_json is not None:
            self.conn.execute(
                "INSERT INTO events (session_id, op, axiom_hash, axiom_json) VALUES (?, ?, ?, jsonb(?))",
                (self._session_id, op, axiom_hash, axiom_json),
            )
        else:
            self.conn.execute(
                "INSERT INTO events (session_id, op, axiom_hash) VALUES (?, ?, ?)",
                (self._session_id, op, axiom_hash),
            )

    # -- Axiom operations --

    def add_axioms(self, axioms: list[Axiom]) -> AddResult:
        added: list[HashedAxiom] = []
        skipped: list[HashedAxiom] = []

        with self.conn:
            for axiom in axioms:
                h = content_hash(axiom)
                json_data = axiom.model_dump_json()
                cursor = self.conn.execute(
                    "INSERT OR IGNORE INTO axioms (hash, type, data) VALUES (?, ?, jsonb(?))",
                    (h, axiom.type, json_data),
                )
                ha = HashedAxiom(axiom=axiom, hash=h)

                if cursor.rowcount == 0:
                    skipped.append(ha)
                    continue

                added.append(ha)
                self._log_event("add", h, json_data)
                self._populate_indexes(axiom, cursor.lastrowid)

        return AddResult(added=added, skipped=skipped)

    def remove_by_hash_prefix(self, hash_prefixes: list[str]) -> RemoveResult:
        to_remove: list[HashedAxiom] = []

        for prefix in hash_prefixes:
            rows = self.conn.execute(
                "SELECT hash, json(data) FROM axioms WHERE hash GLOB ? || '*'",
                (prefix,),
            ).fetchall()

            if not rows:
                msg = f"[{prefix}] not found"
                raise ValueError(msg)
            if len(rows) > 1:
                matches = ", ".join(r[0][:8] for r in rows)
                msg = f"[{prefix}] matches {len(rows)} axioms: {matches}"
                raise ValueError(msg)

            full_hash, json_data = rows[0]
            axiom = _AXIOM_ADAPTER.validate_json(json_data)
            to_remove.append(HashedAxiom(axiom=axiom, hash=full_hash))

        with self.conn:
            for ha in to_remove:
                self._log_event("del", ha.hash)
                # CASCADE handles axiom_entities, entity_text, axiom_text
                self.conn.execute("DELETE FROM axioms WHERE hash = ?", (ha.hash,))

        return RemoveResult(removed=to_remove)

    def annotate_axiom(
        self,
        axiom_hash: str,
        add_annotations: list[Annotation] | None = None,
        remove_annotations: list[Annotation] | None = None,
    ) -> HashedAxiom:
        """Update annotations on an axiom in-place. Hash does not change."""
        add_annotations = add_annotations or []
        remove_annotations = remove_annotations or []

        row = self.conn.execute(
            "SELECT id, json(data) FROM axioms WHERE hash = ?", (axiom_hash,)
        ).fetchone()
        if row is None:
            msg = f"No axiom with hash {axiom_hash!r}"
            raise ValueError(msg)

        axiom_id, json_data = row
        axiom = _AXIOM_ADAPTER.validate_json(json_data)

        current = list(axiom.annotations)
        for ann in remove_annotations:
            if ann in current:
                current.remove(ann)
        for ann in add_annotations:
            if ann not in current:
                current.append(ann)

        updated = axiom.model_copy(update={"annotations": tuple(current)})
        new_json = updated.model_dump_json()

        with self.conn:
            self._log_event("del", axiom_hash)
            self.conn.execute(
                "UPDATE axioms SET data = jsonb(?) WHERE id = ?", (new_json, axiom_id)
            )
            self._log_event("add", axiom_hash, new_json)

            # Rebuild axiom_text for this axiom
            self.conn.execute("DELETE FROM axiom_text WHERE axiom_id = ?", (axiom_id,))
            self.conn.executemany(
                "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
                [
                    (axiom_id, _extract_annotation_value(ann.value), str(ann.property))
                    for ann in updated.annotations
                ],
            )

        return HashedAxiom(axiom=updated, hash=axiom_hash)

    # -- Index population --

    def _populate_indexes(self, axiom: Axiom, axiom_id: int) -> None:
        entity_rows = []
        text_rows = []
        seen_iris: set[str] = set()

        for iri, role in extract_from_axiom(axiom):
            iri_str = str(iri)
            role_val = role.value if isinstance(role, EntityType) else role
            entity_rows.append((axiom_id, iri_str, role_val))
            if iri_str not in seen_iris:
                seen_iris.add(iri_str)
                text_rows.append((axiom_id, iri_str, iri.local_name, "local_name"))

        if isinstance(axiom, AnnotationAssertion):
            text_rows.append(
                (
                    axiom_id,
                    str(axiom.subject),
                    _extract_annotation_value(axiom.value),
                    str(axiom.property),
                )
            )

        self.conn.executemany(
            "INSERT INTO axiom_entities (axiom_id, entity_iri, role) VALUES (?, ?, ?)",
            entity_rows,
        )
        self.conn.executemany(
            "INSERT INTO entity_text (axiom_id, entity_iri, text, property) VALUES (?, ?, ?, ?)",
            text_rows,
        )

        axiom_text_rows = [
            (axiom_id, _extract_annotation_value(ann.value), str(ann.property))
            for ann in axiom.annotations
        ]
        if axiom_text_rows:
            self.conn.executemany(
                "INSERT INTO axiom_text (axiom_id, text, property) VALUES (?, ?, ?)",
                axiom_text_rows,
            )

    # -- Entity queries --

    def get_entity(self, iri: IRI) -> EntityInfo | None:
        iri_str = str(iri)

        if (
            self.conn.execute(
                "SELECT 1 FROM axiom_entities WHERE entity_iri = ? LIMIT 1", (iri_str,)
            ).fetchone()
            is None
        ):
            return None

        roles = {
            EntityType(r[0])
            for r in self.conn.execute(
                "SELECT DISTINCT role FROM axiom_entities WHERE entity_iri = ? AND role IS NOT NULL",
                (iri_str,),
            )
        }

        annotations = [
            AnnotationRow(property=IRI(r[0]), value=r[1])
            for r in self.conn.execute(
                "SELECT DISTINCT property, text FROM entity_text WHERE entity_iri = ? AND property != 'local_name'",
                (iri_str,),
            )
        ]

        axiom_counts = Counter(
            {
                r[0]: r[1]
                for r in self.conn.execute(
                    """
                SELECT a.type, COUNT(DISTINCT a.id)
                FROM axiom_entities ae
                JOIN axioms a ON ae.axiom_id = a.id
                WHERE ae.entity_iri = ? AND a.type != 'AnnotationAssertion'
                GROUP BY a.type
                """,
                    (iri_str,),
                )
            }
        )

        return EntityInfo(roles=roles, annotations=annotations, axiom_counts=axiom_counts)

    # -- Search --

    def search_entities(
        self,
        query: str | None = None,
        role: str | None = None,
        namespace: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> EntitySearchPage:
        if query is None:
            return self._list_entities(role=role, namespace=namespace, limit=limit, offset=offset)
        return self._text_search_entities(
            query=query, role=role, namespace=namespace, limit=limit, offset=offset
        )

    def _list_entities(
        self,
        role: str | None,
        namespace: str | None,
        limit: int,
        offset: int,
    ) -> EntitySearchPage:
        """List entities matching structural filters (no text query)."""
        conditions = ["ae.role IS NOT NULL"]
        params: list[str | int] = []

        if role is not None:
            conditions.append("ae.role = ?")
            params.append(role)
        if namespace is not None:
            conditions.append("ae.entity_iri GLOB ?")
            params.append(f"{namespace}:*")

        where = " AND ".join(conditions)

        total = self.conn.execute(
            f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae WHERE {where}",
            params,
        ).fetchone()[0]

        page_iris = [
            r[0]
            for r in self.conn.execute(
                f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae WHERE {where} ORDER BY ae.entity_iri LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
        ]
        if not page_iris:
            return EntitySearchPage(matches=[], total=total)

        display = self._batch_fetch_entity_display(page_iris)
        matches = [
            EntityMatch(
                iri=IRI(iri_str),
                roles=display[iri_str][0],
                annotations=display[iri_str][1],
                match_source="list",
                match_quality="exact",
            )
            for iri_str in page_iris
            if iri_str in display
        ]
        return EntitySearchPage(matches=matches, total=total)

    def _text_search_entities(
        self,
        query: str,
        role: str | None,
        namespace: str | None,
        limit: int,
        offset: int,
    ) -> EntitySearchPage:
        """Search entities by text, then apply structural filters."""
        matches: dict[str, tuple[str, str]] = {}
        fetch_limit = limit * 3

        # Collect candidate matches from text indexes
        self._collect_text_matches(query, "local_name", "iri", matches, fetch_limit)
        self._collect_text_matches_annotations(query, matches, fetch_limit)

        # Apply structural filters in batch
        if role is not None and matches:
            role_iris = self._batch_check_roles(list(matches.keys()), role)
            matches = {k: v for k, v in matches.items() if k in role_iris}
        if namespace is not None:
            matches = {k: v for k, v in matches.items() if k.startswith(f"{namespace}:")}

        # Sort and paginate
        quality_order = {"exact": 0, "substring": 1}
        source_order = {"iri": 0, "annotation": 1}
        sorted_iris = sorted(
            matches.keys(),
            key=lambda k: (
                quality_order.get(matches[k][1], 9),
                source_order.get(matches[k][0], 9),
                k,
            ),
        )

        total = len(sorted_iris)
        page_iris = sorted_iris[offset : offset + limit]
        if not page_iris:
            return EntitySearchPage(matches=[], total=total)

        display = self._batch_fetch_entity_display(page_iris)
        result_matches = [
            EntityMatch(
                iri=IRI(iri_str),
                roles=display.get(iri_str, (set(), []))[0],
                annotations=display.get(iri_str, (set(), []))[1],
                match_source=matches[iri_str][0],
                match_quality=matches[iri_str][1],
            )
            for iri_str in page_iris
        ]
        return EntitySearchPage(matches=result_matches, total=total)

    def _batch_fetch_entity_display(
        self, iris: list[str]
    ) -> dict[str, tuple[set[EntityType], list[AnnotationRow]]]:
        """Fetch roles + annotations for multiple entities in two queries."""
        placeholders = ",".join("?" for _ in iris)

        roles_by_iri: dict[str, set[EntityType]] = {}
        for iri_str, role_val in self.conn.execute(
            f"SELECT entity_iri, role FROM axiom_entities WHERE entity_iri IN ({placeholders}) AND role IS NOT NULL",
            iris,
        ):
            roles_by_iri.setdefault(iri_str, set()).add(EntityType(role_val))

        anns_by_iri: dict[str, list[AnnotationRow]] = {}
        for iri_str, prop, text in self.conn.execute(
            f"SELECT DISTINCT entity_iri, property, text FROM entity_text WHERE entity_iri IN ({placeholders}) AND property != 'local_name'",
            iris,
        ):
            anns_by_iri.setdefault(iri_str, []).append(
                AnnotationRow(property=IRI(prop), value=text)
            )

        return {
            iri_str: (roles_by_iri.get(iri_str, set()), anns_by_iri.get(iri_str, []))
            for iri_str in iris
        }

    def _batch_check_roles(self, iris: list[str], role: str) -> set[str]:
        """Check which IRIs have a given role in one query."""
        if not iris:
            return set()
        placeholders = ",".join("?" for _ in iris)
        return {
            r[0]
            for r in self.conn.execute(
                f"SELECT DISTINCT entity_iri FROM axiom_entities WHERE entity_iri IN ({placeholders}) AND role = ?",
                [*iris, role],
            )
        }

    def _collect_text_matches(
        self,
        query: str,
        property_filter: str,
        source_label: str,
        matches: dict[str, tuple[str, str]],
        limit: int,
    ) -> None:
        for (iri_str,) in self.conn.execute(
            "SELECT DISTINCT entity_iri FROM entity_text WHERE property = ? AND text = ? LIMIT ?",
            (property_filter, query, limit),
        ):
            if iri_str not in matches:
                matches[iri_str] = (source_label, "exact")

        for (iri_str,) in self.conn.execute(
            "SELECT DISTINCT entity_iri FROM entity_text WHERE property = ? AND text LIKE '%' || ? || '%' LIMIT ?",
            (property_filter, query, limit),
        ):
            if iri_str not in matches:
                matches[iri_str] = (source_label, "substring")

    def _collect_text_matches_annotations(
        self, query: str, matches: dict[str, tuple[str, str]], limit: int
    ) -> None:
        for (iri_str,) in self.conn.execute(
            "SELECT DISTINCT entity_iri FROM entity_text WHERE property != 'local_name' AND text = ? LIMIT ?",
            (query, limit),
        ):
            if iri_str not in matches:
                matches[iri_str] = ("annotation", "exact")

        for (iri_str,) in self.conn.execute(
            "SELECT DISTINCT entity_iri FROM entity_text WHERE property != 'local_name' AND text LIKE '%' || ? || '%' LIMIT ?",
            (query, limit),
        ):
            if iri_str not in matches:
                matches[iri_str] = ("annotation", "substring")

    def search_axioms(
        self,
        iri: IRI | None = None,
        axiom_types: list[str] | None = None,
        annotation_query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SearchPage:
        if iri is not None:
            base_from = "axioms a JOIN axiom_entities ae ON ae.axiom_id = a.id"
            conditions = ["ae.entity_iri = ?"]
            params: list[str | int] = [str(iri)]
        elif annotation_query is not None:
            base_from = "axioms a JOIN axiom_text at ON at.axiom_id = a.id"
            conditions = ["at.text LIKE '%' || ? || '%'"]
            params = [annotation_query]
        else:
            base_from = "axioms a"
            conditions = []
            params = []

        if axiom_types:
            placeholders = ",".join("?" for _ in axiom_types)
            conditions.append(f"a.type IN ({placeholders})")
            params.extend(axiom_types)

        if iri is not None and annotation_query is not None:
            conditions.append(
                "a.id IN (SELECT axiom_id FROM axiom_text WHERE text LIKE '%' || ? || '%')"
            )
            params.append(annotation_query)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        total = self.conn.execute(
            f"SELECT COUNT(DISTINCT a.id) FROM {base_from}{where}", params
        ).fetchone()[0]

        axioms = [
            HashedAxiom(axiom=_AXIOM_ADAPTER.validate_json(data), hash=h)
            for h, data in self.conn.execute(
                f"SELECT DISTINCT a.hash, json(a.data) FROM {base_from}{where} ORDER BY a.id LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
        ]

        return SearchPage(axioms=axioms, total=total)

    # -- Prefix management --

    def _get_metadata(self) -> dict:
        row = self.conn.execute("SELECT data FROM metadata WHERE id = 1").fetchone()
        if row is None:
            return {}
        return json.loads(row[0])

    def _set_metadata(self, data: dict) -> None:
        with self.conn:
            self.conn.execute("UPDATE metadata SET data = ? WHERE id = 1", (json.dumps(data),))

    def list_prefixes(self) -> dict[str, str]:
        return dict(self._get_metadata().get("prefixes", {}))

    def set_prefix(self, name: str, iri: str) -> None:
        meta = self._get_metadata()
        prefixes = meta.get("prefixes", {})
        prefixes[name] = iri
        meta["prefixes"] = prefixes
        self._set_metadata(meta)

    def remove_prefix(self, name: str) -> None:
        meta = self._get_metadata()
        prefixes = meta.get("prefixes", {})
        if name not in prefixes:
            msg = f"no prefix {name!r}"
            raise ValueError(msg)
        del prefixes[name]
        meta["prefixes"] = prefixes
        self._set_metadata(meta)

    # -- Export --

    def export_jsonl(self, output_path: Path) -> int:
        count = 0
        with Path(output_path).open("w") as f:
            for (json_text,) in self.conn.execute("SELECT json(data) FROM axioms ORDER BY hash"):
                f.write(json_text)
                f.write("\n")
                count += 1
        return count

    # -- Summaries --

    def axiom_summary(self) -> Counter[str]:
        return Counter(
            {
                r[0]: r[1]
                for r in self.conn.execute("SELECT type, COUNT(*) FROM axioms GROUP BY type")
            }
        )

    def entity_summary(self) -> tuple[int, Counter[str]]:
        total = self.conn.execute(
            "SELECT COUNT(DISTINCT entity_iri) FROM axiom_entities"
        ).fetchone()[0]
        role_counts = Counter(
            {
                r[0]: r[1]
                for r in self.conn.execute(
                    "SELECT role, COUNT(DISTINCT entity_iri) FROM axiom_entities WHERE role IS NOT NULL GROUP BY role"
                )
            }
        )
        return total, role_counts
