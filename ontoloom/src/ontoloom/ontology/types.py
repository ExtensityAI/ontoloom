from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from ontoloom.ontology.models.axioms import Axiom
from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.literals import IRI

MatchSource = Literal["iri", "annotation", "list"]
MatchQuality = Literal["exact", "substring"]


class Position(StrEnum):
    """Structural role an entity plays within an axiom.

    18 values: 17 stored in axiom_entities.position + ANY (query-time only).
    """

    # Query-time only (never stored in DB)
    ANY = "any"

    # SubClassOf — named superclass
    SUB_CLASS = "sub_class"
    SUPER_CLASS = "super_class"

    # Class expression restrictions (ObjectSomeValuesFrom, ObjectHasValue, etc.)
    RESTRICTION_PROPERTY = "restriction_property"
    FILLER = "filler"

    # Sub*PropertyOf
    SUB_PROPERTY = "sub_property"
    SUPER_PROPERTY = "super_property"

    # SubObjectPropertyOfChain
    CHAIN_MEMBER = "chain_member"

    # AnnotationAssertion
    SUBJECT = "subject"
    PROPERTY = "property"
    VALUE = "value"

    # *Domain / *Range
    DOMAIN = "domain"
    RANGE = "range"

    # ObjectPropertyAssertion
    SOURCE = "source"
    TARGET = "target"

    # ClassAssertion
    INDIVIDUAL = "individual"
    CLASS = "class"

    # EquivalentClasses, DisjointClasses, SameIndividual, DifferentIndividuals
    MEMBER = "member"

    # Declaration
    ENTITY = "entity"


class SelectionKind(StrEnum):
    """Named sets saved from search results for later operations.

    AXIOMS: set of axiom hashes — scope axiom searches, set algebra, export subsets, mass deletion.
    ENTITIES: set of entity IRIs — scope entity/axiom searches, set algebra, convert to axiom selections.
    """

    AXIOMS = "axioms"
    ENTITIES = "entities"


class ShowFilter(StrEnum):
    """Filter for read_selection item visibility.

    ALL: show all items (present and missing).
    PRESENT: only items still in ontology.
    MISSING: only items no longer found (e.g. deleted axioms). Use to audit selections after modifications.
    """

    ALL = "all"
    PRESENT = "present"
    MISSING = "missing"


@dataclass(frozen=True)
class SelectionMeta:
    name: str
    kind: SelectionKind
    hash: str
    cardinality: int
    source: str = ""


@dataclass(frozen=True)
class SelectionItem:
    key: str
    missing: bool
    axiom: Axiom | None = None
    role: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class SelectionPage:
    meta: SelectionMeta
    items: list[SelectionItem] = field(default_factory=list)
    total_filtered: int = 0
    present: int = 0
    missing: int = 0
    show: ShowFilter = ShowFilter.ALL


@dataclass
class AnnotationRow:
    property: IRI
    value: str


@dataclass
class EntityInfo:
    roles: set[EntityType]
    annotations: list[AnnotationRow]
    axiom_counts: Counter[str]


@dataclass
class EntityMatch:
    iri: IRI
    roles: set[EntityType]
    annotations: list[AnnotationRow]
    match_source: MatchSource
    match_quality: MatchQuality


@dataclass
class EntitySearchPage:
    matches: list[EntityMatch]
    total: int


@dataclass
class HashedAxiom:
    axiom: Axiom
    hash: str


@dataclass
class AddResult:
    added: list[HashedAxiom]
    skipped: list[HashedAxiom]


@dataclass
class RemoveResult:
    removed: list[HashedAxiom]


@dataclass
class DuplicateResult:
    groups: list[tuple[str, list[str]]]
    total_groups: int
    affected_iris: list[str]


@dataclass
class ReplaceResult:
    old_hash: str
    new_hash: str
    was_noop: bool  # True if new_hash == old_hash


@dataclass
class RenameResult:
    old_iri: str
    new_iri: str
    replaced: list[ReplaceResult]
    batch_id: str
