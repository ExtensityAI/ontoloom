import pytest
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
)

# -- EntitySelectionName.parse / bare --


def test_entity_selection_name_parse_roundtrip():
    ref = EntitySelectionName("entities:my_sel")
    assert str(ref) == "entities:my_sel"


def test_entity_selection_name_first_colon_split():
    ref = EntitySelectionName("entities:ns:dogs")
    assert ref.bare == "ns:dogs"


def test_entity_selection_name_bare():
    ref = EntitySelectionName("entities:my_sel")
    assert ref.bare == "my_sel"


def test_entity_selection_name_rejects_axiom_prefix():
    with pytest.raises(ValueError):
        EntitySelectionName("axioms:my_sel")


def test_entity_selection_name_rejects_unknown_prefix():
    with pytest.raises(ValueError):
        EntitySelectionName("blobs:my_sel")


def test_entity_selection_name_rejects_missing_colon():
    with pytest.raises(ValueError):
        EntitySelectionName("entities_my_sel")


def test_entity_selection_name_rejects_empty_bare():
    with pytest.raises(ValueError):
        EntitySelectionName("entities:")


def test_entity_selection_name_rejects_invalid_chars():
    with pytest.raises(ValueError):
        EntitySelectionName("entities:bad name")


def test_entity_selection_name_rejects_digit_start():
    with pytest.raises(ValueError):
        EntitySelectionName("entities:1invalid")


# -- AxiomSelectionName.parse / bare --


def test_axiom_selection_name_parse_roundtrip():
    ref = AxiomSelectionName("axioms:my_sel")
    assert str(ref) == "axioms:my_sel"


def test_axiom_selection_name_first_colon_split():
    ref = AxiomSelectionName("axioms:ns:dogs")
    assert ref.bare == "ns:dogs"


def test_axiom_selection_name_rejects_entity_prefix():
    with pytest.raises(ValueError):
        AxiomSelectionName("entities:my_sel")
