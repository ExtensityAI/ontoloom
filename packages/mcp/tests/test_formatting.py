"""Golden-string tests for the shared formatting vocabulary helpers."""

from ontoloom.axioms.hashing import AxiomHash, short_hash
from ontoloom.axioms.types import HashedAxiom
from ontoloom.owl.axioms import SubClassOf
from ontoloom.owl.iri import IRI
from ontoloom.selections.types import SelectionKind
from ontoloom_mcp.components.formatting import (
    Ref,
    _format_axiom_line,
    format_drift,
    format_kinded_count,
    format_missing_axiom_line,
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


def test_axiom_line_present_with_label_hint_unchanged():
    ha = HashedAxiom.of(SubClassOf(sub_class=IRI("ex:Dog"), super_class=IRI("ex:Animal")))
    refs = (Ref(iri=IRI("ex:Dog"), label="Dog"),)
    assert _format_axiom_line(ha, refs) == (
        f'[{short_hash(ha.hash)}] SubClassOf(ex:Dog, ex:Animal)  # ex:Dog "Dog"'
    )


def test_missing_axiom_line_renders_bracketed_short_hash():
    full = AxiomHash("a1b2c3d4e5f6" + "0" * 52)
    assert format_missing_axiom_line(full) == "[a1b2c3d4e5f6] *missing*"
