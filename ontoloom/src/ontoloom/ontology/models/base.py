from typing import ClassVar, Final

from ontoloom.ontology.models._pydantic import FrozenModel, TaggedModel
from ontoloom.ontology.models.literals import Annotation

TYPE_FIELD: Final = "type"
ANNOTATIONS_FIELD: Final = "annotations"

# Walkers that treat annotations as non-content (canonical, codegen, pattern match).
WALKER_SKIP: Final = frozenset({TYPE_FIELD, ANNOTATIONS_FIELD})
# Walkers that must visit annotations (extract.py: annotations contain entity IRIs).
ANNOTATION_WALKER_SKIP: Final = frozenset({TYPE_FIELD})


class BaseClassExpression(TaggedModel):
    pass


class BaseAxiom(TaggedModel):
    annotations: tuple[Annotation, ...] = ()


class BasePattern(FrozenModel):
    """Common base for the generated axiom and expression pattern classes.

    Lets `isinstance(val, BasePattern)` narrow pattern values without listing
    every concrete class. `Contains` is intentionally NOT a BasePattern — it's
    a tuple-matcher with different semantics, handled in its own dispatch arm.

    Each generated pattern sets `axiom_type` to the OWL type string it matches
    (`NamedClassPattern.axiom_type == "NamedClass"`), so dispatch can read
    `pattern.axiom_type` directly instead of stripping `"Pattern"` from
    `pattern.type` at every site.
    """

    axiom_type: ClassVar[str]
