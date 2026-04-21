"""SQLite-based ontology storage with derived index tables and silent event log."""

import importlib.resources
import json
import re
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
_HEX_RE = re.compile(r"^[0-9a-f]*$")


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
        try:
            _apply_pragmas(conn)
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO metadata (id, data) VALUES (1, ?)",
                ('{"prefixes": {}}',),
            )
        finally:
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
        for prefix in hash_prefixes:
            if not _HEX_RE.match(prefix):
                msg = f"[{prefix}] is not a valid hex hash prefix"
                raise ValueError(msg)

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

    def remove_by_selection(self, name: str, hash_prefix: str):
        """Remove axioms referenced by an axiom selection. Best-effort: skips missing."""
        sel = self._verify_selection_hash(name, hash_prefix)
        if sel["kind"] != "axioms":
            msg = f"remove_axioms requires an axiom selection, but {name!r} is an entity selection."
            raise ValueError(msg)

        items = [
            r[0]
            for r in self.conn.execute(
                "SELECT item FROM selection_items WHERE selection_name = ?", (name,)
            )
        ]

        removed: list[HashedAxiom] = []
        absent = 0
        with self.conn:
            for h in items:
                row = self.conn.execute(
                    "SELECT hash, json(data) FROM axioms WHERE hash = ?", (h,)
                ).fetchone()
                if row is None:
                    absent += 1
                    continue
                full_hash, json_data = row
                axiom = _AXIOM_ADAPTER.validate_json(json_data)
                self._log_event("del", full_hash)
                self.conn.execute("DELETE FROM axioms WHERE hash = ?", (full_hash,))
                removed.append(HashedAxiom(axiom=axiom, hash=full_hash))

        return removed, absent

    def annotate_axiom(
        self,
        axiom_hash: str,
        add_annotations: list[Annotation] | None = None,
        remove_annotations: list[Annotation] | None = None,
    ):
        """Only modifies BaseAxiom.annotations metadata — does not touch entity_text
        (which indexes axiom structure: IRIs and AnnotationAssertion values).

        Accepts full hash or unambiguous prefix (like remove_by_hash_prefix)."""
        add_annotations = add_annotations or []
        remove_annotations = remove_annotations or []

        with self.conn:
            row = self.conn.execute(
                "SELECT id, hash, json(data) FROM axioms WHERE hash GLOB ? || '*'",
                (axiom_hash,),
            ).fetchone()
            if row is None:
                msg = f"No axiom matching hash {axiom_hash!r}"
                raise ValueError(msg)

            # Check for ambiguous prefix
            count = self.conn.execute(
                "SELECT COUNT(*) FROM axioms WHERE hash GLOB ? || '*'",
                (axiom_hash,),
            ).fetchone()[0]
            if count > 1:
                msg = f"Hash prefix {axiom_hash!r} matches {count} axioms — use a longer prefix"
                raise ValueError(msg)

            axiom_id, axiom_hash, json_data = row
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

    def get_entity(self, iri: IRI, *, within: str | None = None) -> EntityInfo | None:
        iri_str = str(iri)

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

        # within kind='axioms' scopes axiom counts to that selection
        extra_join = ""
        extra_params: list[str] = []
        if within is not None:
            sel = self._get_selection(within)
            if sel["kind"] == "axioms":
                extra_join = (
                    " JOIN selection_items si_w ON si_w.item = a.hash AND si_w.selection_name = ?"
                )
                extra_params.append(within)
            # kind='entities' is a no-op for get_entity

        axiom_counts = Counter(
            {
                r[0]: r[1]
                for r in self.conn.execute(
                    f"""
                SELECT a.type, COUNT(DISTINCT a.id)
                FROM axiom_entities ae
                JOIN axioms a ON ae.axiom_id = a.id{extra_join}
                WHERE ae.entity_iri = ? AND a.type != 'AnnotationAssertion'
                GROUP BY a.type
                """,
                    (*extra_params, iri_str),
                )
            }
        )

        if not roles and not annotations and not axiom_counts:
            return None
        return EntityInfo(roles=roles, annotations=annotations, axiom_counts=axiom_counts)

    def get_entity_axiom_hashes(self, iri: IRI, *, within: str | None = None) -> list[str]:
        """Return all axiom hashes for an entity. For get_entity select workflow."""
        iri_str = str(iri)
        extra_join = ""
        extra_params: list[str] = []
        if within is not None:
            sel = self._get_selection(within)
            if sel["kind"] == "axioms":
                extra_join = (
                    " JOIN selection_items si_w ON si_w.item = a.hash AND si_w.selection_name = ?"
                )
                extra_params.append(within)

        return [
            r[0]
            for r in self.conn.execute(
                f"SELECT DISTINCT a.hash FROM axiom_entities ae "
                f"JOIN axioms a ON ae.axiom_id = a.id{extra_join} "
                f"WHERE ae.entity_iri = ?",
                (*extra_params, iri_str),
            )
        ]

    # -- Search --

    def search_entities(
        self,
        query: str | None = None,
        role: str | None = None,
        namespace: str | None = None,
        within: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        if query is None:
            return self._list_entities(
                role=role, namespace=namespace, within=within, limit=limit, offset=offset
            )
        return self._text_search_entities(
            query=query, role=role, namespace=namespace, within=within, limit=limit, offset=offset
        )

    def _list_entities(
        self, role: str | None, namespace: str | None, within: str | None, limit: int, offset: int
    ):
        conditions = ["ae.role IS NOT NULL"]
        params: list[str | int] = []
        joins = ""

        if within is not None:
            sel = self._get_selection(within)
            if sel["kind"] == "entities":
                joins = " JOIN selection_items si_w ON si_w.item = ae.entity_iri AND si_w.selection_name = ?"
                params.append(within)
            else:  # axioms — entities mentioned in those axioms
                joins = (
                    " JOIN axioms a_w ON a_w.id = ae.axiom_id"
                    " JOIN selection_items si_w ON si_w.item = a_w.hash AND si_w.selection_name = ?"
                )
                params.append(within)

        if role is not None:
            conditions.append("ae.role = ?")
            params.append(role)
        if namespace is not None:
            conditions.append("ae.entity_iri LIKE ? || ':%'")
            params.append(namespace)

        where = " AND ".join(conditions)

        total = self.conn.execute(
            f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae{joins} WHERE {where}",
            params,
        ).fetchone()[0]

        page_iris = [
            r[0]
            for r in self.conn.execute(
                f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae{joins} WHERE {where} ORDER BY ae.entity_iri LIMIT ? OFFSET ?",
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
        self,
        query: str,
        role: str | None,
        namespace: str | None,
        within: str | None,
        limit: int,
        offset: int,
    ):
        matches = self._find_text_matches(query, _LOCAL_NAME, "iri")
        matches.update(self._find_text_matches(query, None, "annotation"))

        if within is not None and matches:
            sel = self._get_selection(within)
            if sel["kind"] == "entities":
                allowed = {
                    r[0]
                    for r in self.conn.execute(
                        "SELECT item FROM selection_items WHERE selection_name = ?", (within,)
                    )
                }
            else:  # axioms — entities mentioned in those axioms
                allowed = {
                    r[0]
                    for r in self.conn.execute(
                        "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
                        "JOIN axioms a ON a.id = ae.axiom_id "
                        "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ?",
                        (within,),
                    )
                }
            matches = {k: v for k, v in matches.items() if k in allowed}

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

        query_lower = query.lower()

        for (iri_str,) in self.conn.execute(
            f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND LOWER(text) = ?",
            (prop_param, query_lower),
        ):
            if iri_str not in matches:
                matches[iri_str] = (source_label, "exact")

        for (iri_str,) in self.conn.execute(
            f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND INSTR(LOWER(text), ?) > 0",
            (prop_param, query_lower),
        ):
            if iri_str not in matches:
                matches[iri_str] = (source_label, "substring")

        return matches

    def _build_axiom_search(
        self,
        iri: IRI | None = None,
        axiom_types: list[str] | None = None,
        annotation_query: str | None = None,
        annotation_properties: list[str] | None = None,
        entity_query: str | None = None,
        within: str | None = None,
    ) -> tuple[str, list[str | int]]:
        """Build the FROM...WHERE clause for axiom searches. Returns (base_sql, params)."""
        joins: list[str] = []
        conditions: list[str] = []
        params: list[str | int] = []

        # within: scope to an existing selection
        if within is not None:
            sel = self._get_selection(within)
            if sel["kind"] == "axioms":
                joins.append(
                    "JOIN selection_items si_w ON si_w.item = a.hash AND si_w.selection_name = ?"
                )
                params.append(within)
            else:  # entities
                joins.append("JOIN axiom_entities ae_w ON ae_w.axiom_id = a.id")
                joins.append(
                    "JOIN selection_items si_w ON si_w.item = ae_w.entity_iri AND si_w.selection_name = ?"
                )
                params.append(within)

        if iri is not None:
            joins.append("JOIN axiom_entities ae ON ae.axiom_id = a.id")
            conditions.append("ae.entity_iri = ?")
            params.append(str(iri))

        if annotation_query is not None:
            joins.append("JOIN axiom_text at ON at.axiom_id = a.id")
            conditions.append("INSTR(at.text, ?) > 0")
            params.append(annotation_query)

        if annotation_properties:
            joins.append("JOIN entity_text et ON et.axiom_id = a.id")
            placeholders = ",".join("?" for _ in annotation_properties)
            conditions.append(f"et.property IN ({placeholders})")
            params.extend(annotation_properties)

        # Optimization note: when both iri and entity_query are set,
        # axiom_entities is joined twice (ae + ae_eq). This produces N*M
        # rows before DISTINCT. Acceptable for typical axiom sizes (2-5
        # entities). A future optimization could skip entity_query's join
        # when iri is already set, since iri is strictly more specific.
        if entity_query is not None:
            joins.append("JOIN axiom_entities ae_eq ON ae_eq.axiom_id = a.id")
            conditions.append(
                "ae_eq.entity_iri IN ("
                "SELECT DISTINCT entity_iri FROM entity_text "
                "WHERE INSTR(LOWER(text), LOWER(?)) > 0"
                ")"
            )
            params.append(entity_query)

        if axiom_types:
            placeholders = ",".join("?" for _ in axiom_types)
            conditions.append(f"a.type IN ({placeholders})")
            params.extend(axiom_types)

        join_clause = (" " + " ".join(joins)) if joins else ""
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        base = f"FROM axioms a{join_clause}{where}"
        return base, params

    def search_axioms(
        self,
        iri: IRI | None = None,
        axiom_types: list[str] | None = None,
        annotation_query: str | None = None,
        annotation_properties: list[str] | None = None,
        entity_query: str | None = None,
        within: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        base, params = self._build_axiom_search(
            iri=iri,
            axiom_types=axiom_types,
            annotation_query=annotation_query,
            annotation_properties=annotation_properties,
            entity_query=entity_query,
            within=within,
        )

        total = self.conn.execute(f"SELECT COUNT(DISTINCT a.id) {base}", params).fetchone()[0]

        axioms = [
            HashedAxiom(axiom=_AXIOM_ADAPTER.validate_json(data), hash=h)
            for h, data in self.conn.execute(
                f"SELECT DISTINCT a.hash, json(a.data) {base} ORDER BY a.id LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
        ]

        return SearchPage(axioms=axioms, total=total)

    def collect_axiom_hashes(
        self,
        iri: IRI | None = None,
        axiom_types: list[str] | None = None,
        annotation_query: str | None = None,
        annotation_properties: list[str] | None = None,
        entity_query: str | None = None,
        within: str | None = None,
    ) -> list[str]:
        """Return all matching axiom hashes (no data deserialization). For select workflows."""
        base, params = self._build_axiom_search(
            iri=iri,
            axiom_types=axiom_types,
            annotation_query=annotation_query,
            annotation_properties=annotation_properties,
            entity_query=entity_query,
            within=within,
        )
        return [r[0] for r in self.conn.execute(f"SELECT DISTINCT a.hash {base}", params)]

    def collect_entity_iris(
        self,
        query: str | None = None,
        role: str | None = None,
        namespace: str | None = None,
        within: str | None = None,
    ) -> list[str]:
        """Return all matching entity IRIs (no display data). For select workflows."""
        if query is None:
            # List path: SQL-only
            conditions = ["ae.role IS NOT NULL"]
            params: list[str | int] = []
            joins = ""

            if within is not None:
                sel = self._get_selection(within)
                if sel["kind"] == "entities":
                    joins = " JOIN selection_items si_w ON si_w.item = ae.entity_iri AND si_w.selection_name = ?"
                    params.append(within)
                else:
                    joins = (
                        " JOIN axioms a_w ON a_w.id = ae.axiom_id"
                        " JOIN selection_items si_w ON si_w.item = a_w.hash AND si_w.selection_name = ?"
                    )
                    params.append(within)

            if role is not None:
                conditions.append("ae.role = ?")
                params.append(role)
            if namespace is not None:
                conditions.append("ae.entity_iri LIKE ? || ':%'")
                params.append(namespace)

            where = " AND ".join(conditions)
            return [
                r[0]
                for r in self.conn.execute(
                    f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae{joins} WHERE {where}",
                    params,
                )
            ]

        # Text search path: reuse matching logic
        matches = self._find_text_matches(query, _LOCAL_NAME, "iri")
        matches.update(self._find_text_matches(query, None, "annotation"))

        if within is not None and matches:
            sel = self._get_selection(within)
            if sel["kind"] == "entities":
                allowed = {
                    r[0]
                    for r in self.conn.execute(
                        "SELECT item FROM selection_items WHERE selection_name = ?", (within,)
                    )
                }
            else:
                allowed = {
                    r[0]
                    for r in self.conn.execute(
                        "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
                        "JOIN axioms a ON a.id = ae.axiom_id "
                        "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ?",
                        (within,),
                    )
                }
            matches = {k: v for k, v in matches.items() if k in allowed}

        if role is not None and matches:
            role_iris = self._batch_check_roles(list(matches.keys()), role)
            matches = {k: v for k, v in matches.items() if k in role_iris}
        if namespace is not None:
            prefix = f"{namespace}:"
            matches = {k: v for k, v in matches.items() if k.startswith(prefix)}

        return list(matches.keys())

    # -- Prefix management --

    def _get_metadata(self):
        row = self.conn.execute("SELECT data FROM metadata WHERE id = 1").fetchone()
        if row is None:
            return {}
        return json.loads(row[0])

    def list_prefixes(self):
        return self._get_metadata().get("prefixes", {})

    def set_prefix(self, name: str, iri: str):
        with self.conn:
            meta = self._get_metadata()
            prefixes = meta.get("prefixes", {})
            prefixes[name] = iri
            meta["prefixes"] = prefixes
            self.conn.execute("UPDATE metadata SET data = ? WHERE id = 1", (json.dumps(meta),))

    def remove_prefix(self, name: str):
        with self.conn:
            meta = self._get_metadata()
            prefixes = meta.get("prefixes", {})
            if name not in prefixes:
                msg = f"no prefix {name!r}"
                raise ValueError(msg)
            del prefixes[name]
            meta["prefixes"] = prefixes
            self.conn.execute("UPDATE metadata SET data = ? WHERE id = 1", (json.dumps(meta),))

    # -- Export --

    def export_jsonl(self, output_path: Path, *, select: str | None = None):
        if select is not None:
            sel = self._get_selection(select)
            if sel["kind"] != "axioms":
                msg = f"export_jsonl requires an axiom selection, but {select!r} is an entity selection."
                raise ValueError(msg)
            query = (
                "SELECT json(a.data) FROM axioms a "
                "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                "ORDER BY a.hash"
            )
            params: tuple[str, ...] = (select,)
        else:
            query = "SELECT json(data) FROM axioms ORDER BY hash"
            params = ()

        count = 0
        with output_path.open("w") as f:
            for (json_text,) in self.conn.execute(query, params):
                f.write(json_text)
                f.write("\n")
                count += 1
        return count

    # -- Selections --

    def _selection_hash(self, items: list[str]) -> str:
        """SHA-256 of sorted items, first 8 hex chars.

        If collisions are ever observed (extremely unlikely with selection counts
        in the tens), dynamic hash length can be applied as with axiom hashes.
        """
        import hashlib

        content = "\n".join(sorted(items))
        return hashlib.sha256(content.encode()).hexdigest()[:8]

    def _get_selection(self, name: str):
        row = self.conn.execute(
            "SELECT kind, hash, cardinality FROM selections WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            msg = f"Selection {name!r} does not exist."
            raise ValueError(msg)
        return {"kind": row[0], "hash": row[1], "cardinality": row[2]}

    def _verify_selection_hash(self, name: str, hash_prefix: str):
        sel = self._get_selection(name)
        if not sel["hash"].startswith(hash_prefix):
            msg = (
                f"Selection {name!r} has changed since you last observed it. "
                "Use read_selection or list_selections to verify it still "
                "contains what you expect."
            )
            raise ValueError(msg)
        return sel

    def _write_selection(self, name: str, kind: str, items: list[str], source: str):
        """Write a selection, overwriting if it exists. Returns (hash, cardinality, overwrote)."""
        content_hash = self._selection_hash(items)
        cardinality = len(items)

        overwrote = self.conn.execute(
            "SELECT cardinality FROM selections WHERE name = ?", (name,)
        ).fetchone()

        with self.conn:
            self.conn.execute("DELETE FROM selection_items WHERE selection_name = ?", (name,))
            self.conn.execute("DELETE FROM selections WHERE name = ?", (name,))
            self.conn.execute(
                "INSERT INTO selections (name, kind, hash, cardinality, source) VALUES (?, ?, ?, ?, ?)",
                (name, kind, content_hash, cardinality, source),
            )
            if items:
                self.conn.executemany(
                    "INSERT INTO selection_items (selection_name, item) VALUES (?, ?)",
                    [(name, item) for item in items],
                )

        old_cardinality = overwrote[0] if overwrote else None
        return content_hash, cardinality, old_cardinality

    def list_selections(self):
        return [
            {
                "name": r[0],
                "kind": r[1],
                "hash": r[2],
                "cardinality": r[3],
                "source": r[4],
                "created_at": r[5],
            }
            for r in self.conn.execute(
                "SELECT name, kind, hash, cardinality, source, created_at FROM selections ORDER BY created_at"
            )
        ]

    def read_selection(self, name: str, *, limit: int = 20, offset: int = 0, show: str = "all"):
        sel = self._get_selection(name)
        kind = sel["kind"]

        if kind == "axioms":
            # LEFT JOIN to detect missing axioms
            base = (
                "FROM selection_items si "
                "LEFT JOIN axioms a ON a.hash = si.item "
                "WHERE si.selection_name = ?"
            )
            if show == "present":
                base += " AND a.id IS NOT NULL"
            elif show == "missing":
                base += " AND a.id IS NULL"

            total = self.conn.execute(f"SELECT COUNT(*) {base}", (name,)).fetchone()[0]
            rows = self.conn.execute(
                f"SELECT si.item, json(a.data) {base} ORDER BY si.rowid LIMIT ? OFFSET ?",
                (name, limit, offset),
            ).fetchall()

            # Summary stats (always computed regardless of show filter)
            present_count = self.conn.execute(
                "SELECT COUNT(*) FROM selection_items si "
                "JOIN axioms a ON a.hash = si.item "
                "WHERE si.selection_name = ?",
                (name,),
            ).fetchone()[0]
            missing_count = sel["cardinality"] - present_count

            items = []
            for item_hash, data in rows:
                if data is None:
                    items.append({"hash": item_hash, "missing": True})
                else:
                    items.append(
                        {
                            "hash": item_hash,
                            "missing": False,
                            "axiom": _AXIOM_ADAPTER.validate_json(data),
                        }
                    )

        else:  # entities
            # Entity exists if it has a Declaration axiom
            base = (
                "FROM selection_items si "
                "LEFT JOIN ("
                "  SELECT DISTINCT ae.entity_iri "
                "  FROM axiom_entities ae JOIN axioms a ON a.id = ae.axiom_id "
                "  WHERE a.type = 'Declaration'"
                ") decl ON decl.entity_iri = si.item "
                "WHERE si.selection_name = ?"
            )
            if show == "present":
                base += " AND decl.entity_iri IS NOT NULL"
            elif show == "missing":
                base += " AND decl.entity_iri IS NULL"

            total = self.conn.execute(f"SELECT COUNT(*) {base}", (name,)).fetchone()[0]
            rows = self.conn.execute(
                f"SELECT si.item, decl.entity_iri IS NOT NULL {base} ORDER BY si.rowid LIMIT ? OFFSET ?",
                (name, limit, offset),
            ).fetchall()

            present_count = self.conn.execute(
                "SELECT COUNT(*) FROM selection_items si "
                "JOIN axiom_entities ae ON ae.entity_iri = si.item "
                "JOIN axioms a ON a.id = ae.axiom_id "
                "WHERE si.selection_name = ? AND a.type = 'Declaration'",
                (name,),
            ).fetchone()[0]
            missing_count = sel["cardinality"] - present_count

            items = []
            for iri, is_present in rows:
                items.append({"iri": iri, "missing": not is_present})

        return {
            "name": name,
            "kind": kind,
            "hash": sel["hash"],
            "cardinality": sel["cardinality"],
            "total_filtered": total,
            "present": present_count,
            "missing": missing_count,
            "show": show,
            "items": items,
        }

    def drop_selections(self, names: list[str]):
        """Best-effort drop. Returns (dropped, not_found) lists."""
        dropped = []
        not_found = []
        for name in names:
            row = self.conn.execute(
                "SELECT cardinality FROM selections WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                not_found.append(name)
            else:
                with self.conn:
                    self.conn.execute("DELETE FROM selections WHERE name = ?", (name,))
                dropped.append((name, row[0]))
        return dropped, not_found

    def create_selection(
        self,
        name: str,
        *,
        union: list[str] | None = None,
        intersection: list[str] | None = None,
        difference: list[str] | None = None,
        axioms_for: str | None = None,
        entities_in: str | None = None,
        source: str = "",
    ):
        """Create a selection from set algebra or type conversion."""
        ops = [
            x for x in [union, intersection, difference, axioms_for, entities_in] if x is not None
        ]
        if len(ops) != 1:
            msg = "Exactly one operation must be provided (union, intersection, difference, axioms_for, or entities_in)."
            raise ValueError(msg)

        if union is not None:
            return self._create_from_set_op("union", name, union, source)
        if intersection is not None:
            return self._create_from_set_op("intersection", name, intersection, source)
        if difference is not None:
            return self._create_from_set_op("difference", name, difference, source)
        if axioms_for is not None:
            return self._create_from_conversion(name, axioms_for, "axioms_for", source)
        # entities_in is not None (guaranteed by ops check above)
        return self._create_from_conversion(name, entities_in, "entities_in", source)  # pyright: ignore[reportArgumentType]

    def _create_from_set_op(self, op: str, name: str, inputs: list[str], source: str):
        # Validate inputs exist and are same kind
        kinds = set()
        for input_name in inputs:
            sel = self._get_selection(input_name)
            kinds.add(sel["kind"])
        if len(kinds) > 1:
            details = ", ".join(f"{n!r} ({self._get_selection(n)['kind']})" for n in inputs)
            msg = f"Cannot {op}: all inputs must be the same kind. Got: {details}"
            raise ValueError(msg)
        kind = kinds.pop()

        # Read all input items (including self if name is in inputs)
        match op:
            case "union":
                placeholders = ",".join("?" for _ in inputs)
                items = [
                    r[0]
                    for r in self.conn.execute(
                        f"SELECT DISTINCT item FROM selection_items WHERE selection_name IN ({placeholders})",
                        inputs,
                    )
                ]
            case "intersection":
                first, *rest = inputs
                items_set = {
                    r[0]
                    for r in self.conn.execute(
                        "SELECT item FROM selection_items WHERE selection_name = ?", (first,)
                    )
                }
                for other in rest:
                    other_items = {
                        r[0]
                        for r in self.conn.execute(
                            "SELECT item FROM selection_items WHERE selection_name = ?", (other,)
                        )
                    }
                    items_set &= other_items
                items = list(items_set)
            case "difference":
                first, *rest = inputs
                items_set = {
                    r[0]
                    for r in self.conn.execute(
                        "SELECT item FROM selection_items WHERE selection_name = ?", (first,)
                    )
                }
                for other in rest:
                    other_items = {
                        r[0]
                        for r in self.conn.execute(
                            "SELECT item FROM selection_items WHERE selection_name = ?", (other,)
                        )
                    }
                    items_set -= other_items
                items = list(items_set)
            case _:
                msg = f"Unknown operation: {op}"
                raise ValueError(msg)

        auto_source = source or f"{op}({', '.join(repr(n) for n in inputs)})"
        return self._write_selection(name, kind, items, auto_source)

    def _create_from_conversion(self, name: str, input_name: str, op: str, source: str):
        sel = self._get_selection(input_name)

        if op == "axioms_for":
            if sel["kind"] != "entities":
                msg = f"'axioms_for' requires an entity selection, but {input_name!r} is an axiom selection."
                raise ValueError(msg)
            items = [
                r[0]
                for r in self.conn.execute(
                    "SELECT DISTINCT a.hash FROM axioms a "
                    "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                    "WHERE ae.entity_iri IN (SELECT item FROM selection_items WHERE selection_name = ?)",
                    (input_name,),
                )
            ]
            kind = "axioms"
        else:  # entities_in
            if sel["kind"] != "axioms":
                msg = f"'entities_in' requires an axiom selection, but {input_name!r} is an entity selection."
                raise ValueError(msg)
            items = [
                r[0]
                for r in self.conn.execute(
                    "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
                    "JOIN axioms a ON a.id = ae.axiom_id "
                    "WHERE a.hash IN (SELECT item FROM selection_items WHERE selection_name = ?)",
                    (input_name,),
                )
            ]
            kind = "entities"

        auto_source = source or f"{op}({input_name!r})"
        return self._write_selection(name, kind, items, auto_source)

    # -- Summaries --

    def axiom_summary(self, *, within: str | None = None):
        if within is None:
            return Counter(
                {
                    r[0]: r[1]
                    for r in self.conn.execute("SELECT type, COUNT(*) FROM axioms GROUP BY type")
                }
            )
        sel = self._get_selection(within)
        if sel["kind"] == "axioms":
            return Counter(
                {
                    r[0]: r[1]
                    for r in self.conn.execute(
                        "SELECT a.type, COUNT(*) FROM axioms a "
                        "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                        "GROUP BY a.type",
                        (within,),
                    )
                }
            )
        # entities: count axioms mentioning those entities
        return Counter(
            {
                r[0]: r[1]
                for r in self.conn.execute(
                    "SELECT a.type, COUNT(DISTINCT a.id) FROM axioms a "
                    "JOIN axiom_entities ae ON ae.axiom_id = a.id "
                    "JOIN selection_items si ON si.item = ae.entity_iri AND si.selection_name = ? "
                    "GROUP BY a.type",
                    (within,),
                )
            }
        )

    def entity_summary(self, *, within: str | None = None):
        if within is None:
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

        sel = self._get_selection(within)
        if sel["kind"] == "entities":
            total = self.conn.execute(
                "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
                "JOIN selection_items si ON si.item = ae.entity_iri AND si.selection_name = ?",
                (within,),
            ).fetchone()[0]
            role_counts = Counter(
                {
                    r[0]: r[1]
                    for r in self.conn.execute(
                        "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
                        "JOIN selection_items si ON si.item = ae.entity_iri AND si.selection_name = ? "
                        "WHERE ae.role IS NOT NULL GROUP BY ae.role",
                        (within,),
                    )
                }
            )
        else:  # axioms — entities mentioned in those axioms
            total = self.conn.execute(
                "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
                "JOIN axioms a ON a.id = ae.axiom_id "
                "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ?",
                (within,),
            ).fetchone()[0]
            role_counts = Counter(
                {
                    r[0]: r[1]
                    for r in self.conn.execute(
                        "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
                        "JOIN axioms a ON a.id = ae.axiom_id "
                        "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                        "WHERE ae.role IS NOT NULL GROUP BY ae.role",
                        (within,),
                    )
                }
            )
        return total, role_counts
