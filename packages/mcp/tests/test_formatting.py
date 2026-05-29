"""Golden-string tests for the shared formatting vocabulary helpers."""

from ontoloom.selections.types import SelectionKind
from ontoloom_mcp.components.formatting import (
    format_drift,
    format_kinded_count,
    format_overwrite_note,
)


def test_kinded_count_axioms_singular():
    assert format_kinded_count(SelectionKind.AXIOMS, 1) == "1 axiom"


def test_kinded_count_axioms_plural():
    assert format_kinded_count(SelectionKind.AXIOMS, 2) == "2 axioms"


def test_kinded_count_axioms_zero():
    assert format_kinded_count(SelectionKind.AXIOMS, 0) == "0 axioms"


def test_kinded_count_entities_singular():
    assert format_kinded_count(SelectionKind.ENTITIES, 1) == "1 entity"


def test_kinded_count_entities_plural():
    assert format_kinded_count(SelectionKind.ENTITIES, 12) == "12 entities"


def test_kinded_count_entities_zero():
    assert format_kinded_count(SelectionKind.ENTITIES, 0) == "0 entities"


def test_drift_populated():
    assert format_drift(3, 2) == "3 present, 2 missing"


def test_drift_no_missing_is_empty():
    assert format_drift(5, 0) == ""


def test_overwrite_note_populated_has_leading_space_and_period():
    assert format_overwrite_note(3) == " Replaced previous (3 items)."


def test_overwrite_note_none_is_empty():
    assert format_overwrite_note(None) == ""


def test_overwrite_note_concatenates_directly():
    base = 'Saved 2 axioms to "x".'
    assert base + format_overwrite_note(3) == 'Saved 2 axioms to "x". Replaced previous (3 items).'
