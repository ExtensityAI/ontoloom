from pydantic import ValidationError

from ontoloom.ontology.connection import Metadata, Ontology, escape_like
from ontoloom.ontology.errors import BadRequestError, PrefixNotFoundError, StoreCorruptionError

# A: prefixes are simple, we should just create a prefix table, then metadata can live in a metadata file and not with prefixes like here!


def _get_metadata(
    ont: Ontology,
) -> Metadata:  # A global: again, return type hitns not needed for simple stuff like this
    row = ont.conn.execute("SELECT data FROM metadata WHERE id = 1").fetchone()
    try:
        return Metadata.model_validate_json(row[0])
    except ValidationError as e:
        msg = "metadata row is malformed"
        raise StoreCorruptionError(msg, e) from e


def _save_metadata(ont: Ontology, meta: Metadata) -> None:
    ont.conn.execute("UPDATE metadata SET data = ? WHERE id = 1", (meta.model_dump_json(),))


def list_all(
    ont: Ontology,
) -> dict[
    str, str
]:  # A global: list_all is ambiguous if you import * from prefixes, so make sure it looks similar to all other prefixes functions.
    return _get_metadata(ont).prefixes


def set_prefix(ont: Ontology, name: str, iri: str):
    with ont.conn:
        meta = _get_metadata(ont)
        _save_metadata(ont, meta.model_copy(update={"prefixes": {**meta.prefixes, name: iri}}))


def remove(ont: Ontology, name: str) -> None:
    with ont.conn:
        meta = _get_metadata(ont)
        if name not in meta.prefixes:
            raise PrefixNotFoundError(name)

        # A: there should be a function we can use for this! why do we manually query again here?

        count = ont.conn.execute(
            "SELECT COUNT(DISTINCT entity_iri) FROM axiom_entities "
            "WHERE entity_iri LIKE ? || ':%' ESCAPE '\\'",
            (escape_like(name),),
        ).fetchone()[0]
        if count > 0:
            msg = f"Cannot remove prefix {name!r}: {count} entities still use it."
            raise BadRequestError(msg)

        new_prefixes = {k: v for k, v in meta.prefixes.items() if k != name}
        _save_metadata(ont, meta.model_copy(update={"prefixes": new_prefixes}))


def usage_counts(ont: Ontology) -> dict[str, int]:
    # A: usage_counts is a bad name, also dict[str, int] is kinda bad. not sure what else to use tho!
    """Count how many distinct entities use each registered prefix namespace.

    Entity IRIs are stored as CURIEs (prefix:local_name); a single GROUP BY on
    the substring before the first colon avoids the per-prefix N+1.
    Unregistered prefixes appearing in the DB are dropped on the join.
    """
    registered = list_all(ont)
    db_counts = {  # A global: consider if it makes sense to include iri in axiom_entities as well? like iri and local_name field? talk with me
        row[0]: row[1]
        for row in ont.conn.execute(
            "SELECT substr(entity_iri, 1, instr(entity_iri, ':') - 1) AS prefix, "
            "COUNT(DISTINCT entity_iri) "
            "FROM axiom_entities WHERE instr(entity_iri, ':') > 0 "
            "GROUP BY prefix"
        )
    }
    return {prefix: db_counts.get(prefix, 0) for prefix in registered}
