"""SQLite-based ontology storage with derived index tables and silent event log."""

import importlib.resources
import json
import sqlite3
import uuid
from collections import Counter
from pathlib import Path
from typing import Self

from pydantic import TypeAdapter

from ontoloom.ontology.canonical import axiom_hash
from ontoloom.ontology.extract import iter_axiom_entities
from ontoloom.ontology.models.axioms import AnnotationAssertion, Axiom
from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.literals import (
    IRI,
    Annotation,
    LangLiteral,
    TypedLiteral,
)
from ontoloom.ontology.types import (
    AddResult,
    AnnotationRow,
    EntityInfo,
    EntityMatch,
    EntitySearchPage,
    HashedAxiom,
    RemoveResult,
    SearchPage,
)

_SQL = importlib.resources.files("ontoloom.ontology")
_SCHEMA = _SQL.joinpath("schema.sql").read_text()
_PRAGMAS = _SQL.joinpath("pragmas.sql").read_text()
_AXIOM_ADAPTER: TypeAdapter[Axiom] = TypeAdapter(Axiom)

_LOCAL_NAME = "local_name"


def _extract_annotation_value(value: IRI | TypedLiteral | LangLiteral):
    if isinstance(value, IRI):
        return str(value)
    return value.value


def _apply_pragmas(conn: sqlite3.Connection):
    was_autocommit = conn.autocommit
    conn.autocommit = True
    for line in _PRAGMAS.strip().splitlines():
        line = line.strip()
        if line:
            conn.execute(line)
    conn.autocommit = was_autocommit


class StoreNotOpenError(RuntimeError):
    pass


class OntologyStore:
    """Must be used as a context manager."""

    @classmethod
    def create(cls, path: Path) -> Self:
        """Create a new empty ontology database. Returns an unopened store."""
        if path.exists():
            msg = f"'{path}' already exists."
            raise FileExistsError(msg)
        conn = sqlite3.connect(str(path), autocommit=True)
        _apply_pragmas(conn)
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
        _apply_pragmas(self._conn)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn is not None:
            self._conn.rollback()
            self._conn.close()
            self._conn = None

    # -- Event log --

    def _log_event(self, op: str, axiom_hash: str, axiom_json: str | None = None):
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

    def add_axioms(self, axioms: list[Axiom]):
        added: list[HashedAxiom] = []
        skipped: list[HashedAxiom] = []

        with self.conn:
            for axiom in axioms:
                h = axiom_hash(axiom)
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
                axiom_id = cursor.lastrowid
                if axiom_id is None:
                    msg = "INSERT succeeded but lastrowid is None"
                    raise RuntimeError(msg)
                self._log_event("add", h, json_data)
                self._populate_indexes(axiom, axiom_id)

        return AddResult(added=added, skipped=skipped)

    def remove_by_hash_prefix(self, hash_prefixes: list[str]):
        with self.conn:
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

            for ha in to_remove:
                self._log_event("del", ha.hash)
                self.conn.execute("DELETE FROM axioms WHERE hash = ?", (ha.hash,))

        return RemoveResult(removed=to_remove)

    def annotate_axiom(
        self,
        axiom_hash: str,
        add_annotations: list[Annotation] | None = None,
        remove_annotations: list[Annotation] | None = None,
    ):
        """Only modifies BaseAxiom.annotations metadata — does not touch entity_text
        (which indexes axiom structure: IRIs and AnnotationAssertion values)."""
        add_annotations = add_annotations or []
        remove_annotations = remove_annotations or []

        with self.conn:
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

            self._log_event("del", axiom_hash)
            self.conn.execute(
                "UPDATE axioms SET data = jsonb(?) WHERE id = ?", (new_json, axiom_id)
            )
            self._log_event("add", axiom_hash, new_json)

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

    def _populate_indexes(self, axiom: Axiom, axiom_id: int):
        entity_rows = []
        text_rows = []
        seen_iris: set[str] = set()

        for iri, role in iter_axiom_entities(axiom):
            iri_str = str(iri)
            role_val = role.value if isinstance(role, EntityType) else role
            entity_rows.append((axiom_id, iri_str, role_val))
            if iri_str not in seen_iris:
                seen_iris.add(iri_str)
                text_rows.append((axiom_id, iri_str, iri.local_name, _LOCAL_NAME))

        # AnnotationAssertion values go to entity_text (keyed to subject entity).
        # Axiom-level metadata annotations go to axiom_text (different table).
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
                "SELECT DISTINCT property, text FROM entity_text WHERE entity_iri = ? AND property != ?",
                (iri_str, _LOCAL_NAME),
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
    ):
        if query is None:
            return self._list_entities(role=role, namespace=namespace, limit=limit, offset=offset)
        return self._text_search_entities(
            query=query, role=role, namespace=namespace, limit=limit, offset=offset
        )

    def _list_entities(self, role: str | None, namespace: str | None, limit: int, offset: int):
        conditions = ["ae.role IS NOT NULL"]
        params: list[str | int] = []

        if role is not None:
            conditions.append("ae.role = ?")
            params.append(role)
        if namespace is not None:
            # Namespace prefixes are validated IRI prefixes (no LIKE metacharacters).
            conditions.append("ae.entity_iri LIKE ? || ':%'")
            params.append(namespace)

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
        return EntitySearchPage(
            matches=[
                EntityMatch(
                    iri=IRI(iri_str),
                    roles=display.get(iri_str, (set(), []))[0],
                    annotations=display.get(iri_str, (set(), []))[1],
                    match_source="list",
                    match_quality="exact",
                )
                for iri_str in page_iris
            ],
            total=total,
        )

    def _text_search_entities(
        self, query: str, role: str | None, namespace: str | None, limit: int, offset: int
    ):
        matches = self._find_text_matches(query, _LOCAL_NAME, "iri")
        matches.update(self._find_text_matches(query, None, "annotation"))

        if role is not None and matches:
            role_iris = self._batch_check_roles(list(matches.keys()), role)
            matches = {k: v for k, v in matches.items() if k in role_iris}
        if namespace is not None:
            prefix = f"{namespace}:"
            matches = {k: v for k, v in matches.items() if k.startswith(prefix)}

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
        return EntitySearchPage(
            matches=[
                EntityMatch(
                    iri=IRI(iri_str),
                    roles=display.get(iri_str, (set(), []))[0],
                    annotations=display.get(iri_str, (set(), []))[1],
                    match_source=matches[iri_str][0],
                    match_quality=matches[iri_str][1],
                )
                for iri_str in page_iris
            ],
            total=total,
        )

    def _batch_fetch_entity_display(self, iris: list[str]):
        placeholders = ",".join("?" for _ in iris)

        roles_by_iri: dict[str, set[EntityType]] = {}
        for iri_str, role_val in self.conn.execute(
            f"SELECT entity_iri, role FROM axiom_entities WHERE entity_iri IN ({placeholders}) AND role IS NOT NULL",
            iris,
        ):
            roles_by_iri.setdefault(iri_str, set()).add(EntityType(role_val))

        anns_by_iri: dict[str, list[AnnotationRow]] = {}
        for iri_str, prop, text in self.conn.execute(
            f"SELECT DISTINCT entity_iri, property, text FROM entity_text WHERE entity_iri IN ({placeholders}) AND property != ?",
            [*iris, _LOCAL_NAME],
        ):
            anns_by_iri.setdefault(iri_str, []).append(
                AnnotationRow(property=IRI(prop), value=text)
            )

        return {
            iri_str: (roles_by_iri.get(iri_str, set()), anns_by_iri.get(iri_str, []))
            for iri_str in iris
        }

    def _batch_check_roles(self, iris: list[str], role: str):
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

    def _find_text_matches(
        self,
        query: str,
        property_filter: str | None,
        source_label: str,
    ) -> dict[str, tuple[str, str]]:
        """Returns {iri: (source_label, quality)}. property_filter=None matches
        all properties except _LOCAL_NAME."""
        if property_filter is not None:
            prop_cond = "property = ?"
            prop_param = property_filter
        else:
            prop_cond = "property != ?"
            prop_param = _LOCAL_NAME

        matches: dict[str, tuple[str, str]] = {}

        for (iri_str,) in self.conn.execute(
            f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND text = ?",
            (prop_param, query),
        ):
            if iri_str not in matches:
                matches[iri_str] = (source_label, "exact")

        for (iri_str,) in self.conn.execute(
            f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND INSTR(text, ?) > 0",
            (prop_param, query),
        ):
            if iri_str not in matches:
                matches[iri_str] = (source_label, "substring")

        return matches

    def search_axioms(
        self,
        iri: IRI | None = None,
        axiom_types: list[str] | None = None,
        annotation_query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        conditions: list[str] = []
        params: list[str | int] = []

        # Build FROM clause based on which filters need joins.
        # When both iri and annotation_query are set, iri determines
        # the join and annotation_query is added as a subquery filter.
        if iri is not None:
            base_from = "axioms a JOIN axiom_entities ae ON ae.axiom_id = a.id"
            conditions.append("ae.entity_iri = ?")
            params.append(str(iri))
        elif annotation_query is not None:
            base_from = "axioms a JOIN axiom_text at ON at.axiom_id = a.id"
            conditions.append("INSTR(at.text, ?) > 0")
            params.append(annotation_query)
        else:
            base_from = "axioms a"

        if axiom_types:
            placeholders = ",".join("?" for _ in axiom_types)
            conditions.append(f"a.type IN ({placeholders})")
            params.extend(axiom_types)

        if iri is not None and annotation_query is not None:
            conditions.append("a.id IN (SELECT axiom_id FROM axiom_text WHERE INSTR(text, ?) > 0)")
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

    def _get_metadata(self):
        row = self.conn.execute("SELECT data FROM metadata WHERE id = 1").fetchone()
        if row is None:
            return {}
        return json.loads(row[0])

    def _set_metadata(self, data: dict):
        with self.conn:
            self.conn.execute("UPDATE metadata SET data = ? WHERE id = 1", (json.dumps(data),))

    def list_prefixes(self):
        return self._get_metadata().get("prefixes", {})

    def set_prefix(self, name: str, iri: str):
        meta = self._get_metadata()
        prefixes = meta.get("prefixes", {})
        prefixes[name] = iri
        meta["prefixes"] = prefixes
        self._set_metadata(meta)

    def remove_prefix(self, name: str):
        meta = self._get_metadata()
        prefixes = meta.get("prefixes", {})
        if name not in prefixes:
            msg = f"no prefix {name!r}"
            raise ValueError(msg)
        del prefixes[name]
        meta["prefixes"] = prefixes
        self._set_metadata(meta)

    # -- Export --

    def export_jsonl(self, output_path: Path):
        count = 0
        with output_path.open("w") as f:
            for (json_text,) in self.conn.execute("SELECT json(data) FROM axioms ORDER BY hash"):
                f.write(json_text)
                f.write("\n")
                count += 1
        return count

    # -- Summaries --

    def axiom_summary(self):
        return Counter(
            {
                r[0]: r[1]
                for r in self.conn.execute("SELECT type, COUNT(*) FROM axioms GROUP BY type")
            }
        )

    def entity_summary(self):
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
