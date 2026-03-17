from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Base for all OWL 2 EL model classes. Immutable by default."""

    model_config = ConfigDict(frozen=True)
