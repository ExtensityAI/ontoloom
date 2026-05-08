import sqlite3

import pytest
from ontoloom.connection import Ontology
from ontoloom.transactions import atomic, dry_run


class BoomError(Exception):
    pass


def _make_ont(tmp_path):
    return Ontology.create(tmp_path / "t.db")


def _read_prefixes(path):
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute(
            "SELECT json_extract(data, '$.prefixes.ex') FROM metadata WHERE id = 1"
        ).fetchone()
        return row[0]
    finally:
        conn.close()


def _set_prefix(s, value: str):
    s.conn.execute(
        "UPDATE metadata SET data = json_set(data, '$.prefixes.ex', ?) WHERE id = 1",
        (value,),
    )


def test_atomic_commits_on_clean_exit(tmp_path):
    ont = _make_ont(tmp_path)
    with atomic(ont) as s:
        _set_prefix(s, "https://example.com/")
    assert _read_prefixes(ont.path) == "https://example.com/"


def test_atomic_rolls_back_on_exception(tmp_path):
    ont = _make_ont(tmp_path)
    with pytest.raises(BoomError), atomic(ont) as s:
        _set_prefix(s, "https://example.com/")
        raise BoomError
    assert _read_prefixes(ont.path) is None


def test_dry_run_rolls_back_on_clean_exit(tmp_path):
    ont = _make_ont(tmp_path)
    with dry_run(ont) as s:
        _set_prefix(s, "https://example.com/")
    assert _read_prefixes(ont.path) is None


def test_dry_run_rolls_back_on_exception(tmp_path):
    ont = _make_ont(tmp_path)
    with pytest.raises(BoomError), dry_run(ont) as s:
        _set_prefix(s, "https://example.com/")
        raise BoomError
    assert _read_prefixes(ont.path) is None


def test_atomic_session_is_not_dry_run(tmp_path):
    ont = _make_ont(tmp_path)
    with atomic(ont) as s:
        assert s.is_dry_run is False


def test_dry_run_session_is_dry_run(tmp_path):
    ont = _make_ont(tmp_path)
    with dry_run(ont) as s:
        assert s.is_dry_run is True


def test_session_id_differs_across_calls(tmp_path):
    ont = _make_ont(tmp_path)
    with atomic(ont) as s1:
        id1 = s1.session_id
    with atomic(ont) as s2:
        id2 = s2.session_id
    with dry_run(ont) as s3:
        id3 = s3.session_id
    assert id1 != id2 != id3 != id1
