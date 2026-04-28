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

        count = ont.conn.execute(
            "SELECT COUNT(DISTINCT entity_iri) FROM axiom_entities WHERE entity_iri LIKE ? || ':%'",
            (name,),
        ).fetchone()[0]
        if count > 0:
            msg = f"Cannot remove prefix {name!r}: {count} entities still use it."
            raise ValueError(msg)

        del prefixes[name]
        meta["prefixes"] = prefixes
        _save_metadata(ont, meta)


def usage_counts(ont: Ontology) -> dict[str, int]:
    """Count how many distinct entities use each registered prefix namespace.

    Entity IRIs are stored as CURIEs (prefix:local_name), so we match on the
    prefix name followed by a colon.
    """
    registered = list_all(ont)
    counts: dict[str, int] = {}
    for prefix in registered:
        row = ont.conn.execute(
            "SELECT COUNT(DISTINCT entity_iri) FROM axiom_entities WHERE entity_iri LIKE ? || ':%'",
            (prefix,),
        ).fetchone()
        counts[prefix] = row[0]
    return counts


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance between two strings."""
    if len(a) < len(b):
        return _edit_distance(b, a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1] + [0] * len(b)
        for j, cb in enumerate(b):
            curr[j + 1] = min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (0 if ca == cb else 1),
            )
        prev = curr
    return prev[len(b)]


def validate_curie(ont: Ontology, iri: str) -> None:
    """Validate that an IRI's prefix is registered. Raises ValueError if not.

    Full URIs (containing '://') are skipped — they are not CURIEs.
    """
    if "://" in iri:
        return

    colon = iri.find(":")
    if colon < 0:
        return

    prefix = iri[:colon]
    registered = list_all(ont)

    if prefix in registered:
        return

    # Find similar prefixes by edit distance
    suggestions = sorted(registered, key=lambda p: _edit_distance(prefix, p))
    suggestion_list = ", ".join(suggestions)

    best = suggestions[0] if suggestions else None
    hint = f" Did you mean {best!r}?" if best else ""

    msg = f"Unknown prefix {prefix!r}.{hint} Registered prefixes: {suggestion_list}"
    raise ValueError(msg)
