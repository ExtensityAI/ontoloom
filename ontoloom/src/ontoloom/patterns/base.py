"""Base for the generated pattern classes."""

from ontoloom.models import FrozenModel


class BasePattern(FrozenModel):
    """Common base for generated axiom and expression pattern classes.

    `cls.axiom_tag()` returns the matched OWL type (the class name minus the
    "Pattern" suffix), e.g. `SubClassOfPattern.axiom_tag() == "SubClassOf"`.
    """

    @classmethod
    def axiom_tag(cls) -> str:
        return cls.__name__.removesuffix("Pattern")
