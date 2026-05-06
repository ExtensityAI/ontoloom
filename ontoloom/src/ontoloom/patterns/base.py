"""Base for the generated pattern classes."""

from typing import ClassVar

from ontoloom.models import FrozenModel


class BasePattern(FrozenModel):
    """Common base for the generated axiom and expression pattern classes.

    Lets `isinstance(val, BasePattern)` narrow pattern values without listing
    every concrete class. Each generated pattern sets `axiom_type` to the OWL
    type string it matches.
    """

    axiom_type: ClassVar[str]
