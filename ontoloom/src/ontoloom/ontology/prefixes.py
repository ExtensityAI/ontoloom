import json

from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.errors import PrefixNotFoundError


def _get_metadata(ont: Ontology):
    row = ont.conn.execute("SELECT data FROM metadata WHERE id = 1").fetchone()
    return json.loads(row[0])


def _save_metadata(ont: Ontology, meta: dict):
    ont.conn.execute("UPDATE metadata SET data = ? WHERE id = 1", (json.dumps(meta),))


def list_all(ont: Ontology) -> dict[str, str]:
    return _get_metadata(ont)["prefixes"]


def set(ont: Ontology, name: str, iri: str) -> None:  # noqa: A001
    with ont.conn:
        meta = _get_metadata(ont)
        prefixes = meta["prefixes"]
        prefixes[name] = iri
        meta["prefixes"] = prefixes
        _save_metadata(ont, meta)


def remove(ont: Ontology, name: str) -> None:
    with ont.conn:
        meta = _get_metadata(ont)
        prefixes = meta["prefixes"]
        if name not in prefixes:
            raise PrefixNotFoundError(name)
        del prefixes[name]
        meta["prefixes"] = prefixes
        _save_metadata(ont, meta)
