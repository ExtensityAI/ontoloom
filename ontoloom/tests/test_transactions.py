import sqlite3
import warnings

import pytest
from ontoloom.connection import Ontology, session


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


def test_commit_persists_writes(tmp_path):
    ont = _make_ont(tmp_path)
    with session(ont) as s:
        _set_prefix(s, "https://example.com/")
        s.commit()
    assert _read_prefixes(ont.path) == "https://example.com/"


def test_rollback_discards_writes(tmp_path):
    ont = _make_ont(tmp_path)
    with session(ont) as s:
        _set_prefix(s, "https://example.com/")
        s.rollback()
    assert _read_prefixes(ont.path) is None


def test_exception_inside_block_rolls_back(tmp_path):
    ont = _make_ont(tmp_path)
    with pytest.raises(BoomError), session(ont) as s:
        _set_prefix(s, "https://example.com/")
        raise BoomError
    assert _read_prefixes(ont.path) is None


def test_exception_after_commit_does_not_unwind(tmp_path):
    ont = _make_ont(tmp_path)
    with pytest.raises(BoomError), session(ont) as s:
        _set_prefix(s, "https://example.com/")
        s.commit()
        raise BoomError
    assert _read_prefixes(ont.path) == "https://example.com/"


def test_forgot_commit_warns_and_rolls_back(tmp_path):
    ont = _make_ont(tmp_path)
    with pytest.warns(RuntimeWarning, match="without commit"), session(ont) as s:
        _set_prefix(s, "https://example.com/")
    assert _read_prefixes(ont.path) is None


def test_forgot_commit_with_no_writes_still_warns(tmp_path):
    ont = _make_ont(tmp_path)
    with pytest.warns(RuntimeWarning, match="without commit"), session(ont):
        pass


def test_no_warning_after_explicit_commit(tmp_path):
    ont = _make_ont(tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with session(ont) as s:
            _set_prefix(s, "https://example.com/")
            s.commit()


def test_no_warning_after_explicit_rollback(tmp_path):
    ont = _make_ont(tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with session(ont) as s:
            _set_prefix(s, "https://example.com/")
            s.rollback()
