from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Base for all OWL 2 EL model classes. Immutable by default."""

    model_config = ConfigDict(frozen=True)


class _BaseClassExpression(FrozenModel):
    """Base for all OWL 2 EL class expressions."""


class _BaseAxiom(FrozenModel):
    """Base for all OWL 2 EL axioms (TBox + RBox + ABox)."""


class _BaseAssertion(_BaseAxiom):
    """Base for all ABox assertions."""
