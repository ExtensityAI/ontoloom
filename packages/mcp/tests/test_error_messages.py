# ruff: noqa: EM101
"""Golden-string tests for `ErrorMiddleware` agent-facing output.

One test per `except` arm. Each test runs a stub tool function (raising the
error directly) through the middleware and asserts the rendered `ToolError`
message byte-for-byte.

The middleware is the single place that composes MCP-enriched messages from
domain errors, so pinning the wording here protects against regressions.
"""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import mcp.types as mt
import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext
from ontoloom.axioms.hashing import (
    AmbiguousHashError,
    AxiomHash,
    AxiomHashPrefix,
    AxiomNotFoundError,
    HashedAxiom,
)
from ontoloom.connection import (
    OntologyExistsError,
    OntologyNotFoundError,
    OntologySchemaError,
)
from ontoloom.entities.reader import EntityNotFoundError
from ontoloom.errors import (
    DatabaseOpenError,
    InternalError,
    OntoloomError,
    StoreCorruptionError,
)
from ontoloom.models import UnionDispatchError
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.owl.prefix_name import PrefixName
from ontoloom.prefixes.types import PrefixInUseError, PrefixNotFoundError, UndeclaredPrefixError
from ontoloom.selections.types import (
    SelectionExistsError,
    SelectionExprError,
    SelectionKindConflictError,
    SelectionName,
    SelectionNotFoundError,
)
from ontoloom_mcp.middleware import ErrorMiddleware
from pydantic import BaseModel


def _run(raiser: Callable[[], Any]) -> str:
    """Run `raiser` through `ErrorMiddleware.on_call_tool`, return the ToolError message.

    Asserts that a ToolError is raised; returns its stringified message.
    """
    mw = ErrorMiddleware()

    async def call_next(context: MiddlewareContext[Any]):  # noqa: ARG001
        return raiser()

    ctx: MiddlewareContext[Any] = MiddlewareContext(
        message=mt.CallToolRequestParams(name="stub", arguments={}),
        method="tools/call",
    )
    with pytest.raises(ToolError) as exc:
        asyncio.run(mw.on_call_tool(ctx, call_next))
    return str(exc.value)


# -- domain-error arms ------------------------------------------------------


def test_entity_not_found_without_near_matches():
    def raiser():
        raise EntityNotFoundError("ex:Ghost")

    assert _run(raiser) == (
        'Entity "ex:Ghost" not found. Use `find_entities` to find entities by name.'
    )


def test_entity_not_found_with_near_matches():
    def raiser():
        raise EntityNotFoundError("ex:Anima", ["ex:Animal", "ex:Animation"])

    assert _run(raiser) == (
        'Entity "ex:Anima" not found. Similar entities: ex:Animal, ex:Animation. '
        "Use `find_entities` to find entities by name."
    )


def test_axiom_not_found():
    def raiser():
        raise AxiomNotFoundError(AxiomHashPrefix("deadbeef"))

    assert _run(raiser) == (
        "No axiom matching hash [deadbeef]. Use `match_axioms` to find axiom hashes."
    )


def test_ambiguous_hash_renders_matches():
    a1 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:X"))
    a2 = Declaration(entity_type=EntityType.CLASS, iri=IRI("ex:Y"))
    matches = (
        ("aa", HashedAxiom(axiom=a1, hash=AxiomHash("aa" + "0" * 62))),
        ("ab", HashedAxiom(axiom=a2, hash=AxiomHash("ab" + "0" * 62))),
    )

    def raiser():
        raise AmbiguousHashError(AxiomHashPrefix("a"), 2, matches)

    msg = _run(raiser)
    assert msg == (
        "[a] matches 2 axioms:\n"
        "  [aa] Declaration(Class, ex:X)\n"
        "  [ab] Declaration(Class, ex:Y)\n"
        "Each shown prefix is the shortest that uniquely identifies its axiom."
    )


def test_ambiguous_hash_truncates_after_ten():
    matches = tuple(
        (
            f"{i:02d}",
            HashedAxiom(
                axiom=Declaration(entity_type=EntityType.CLASS, iri=IRI(f"ex:X{i}")),
                hash=AxiomHash(f"{i:02d}" + "0" * 62),
            ),
        )
        for i in range(12)
    )

    def raiser():
        raise AmbiguousHashError(AxiomHashPrefix("0"), 12, matches)

    msg = _run(raiser)
    assert "... and 2 more." in msg
    assert "[10]" not in msg
    assert "[09]" in msg


def test_prefix_not_found():
    def raiser():
        raise PrefixNotFoundError(PrefixName("foo"))

    assert _run(raiser) == 'No prefix "foo". Use `set_prefix` to define it.'


def test_prefix_in_use():
    def raiser():
        raise PrefixInUseError(PrefixName("ex"), 5)

    assert _run(raiser) == (
        'Prefix "ex" is still used by 5 entities. '
        "Rename or remove those entities first, or use `rename_iri` to migrate them."
    )


def test_undeclared_prefix_single():
    def raiser():
        raise UndeclaredPrefixError(frozenset({PrefixName("ghost")}))

    assert _run(raiser) == (
        'Undeclared prefix(es): "ghost". '
        "Use `set_prefix` to declare them, or use a built-in prefix "
        "('rdf', 'rdfs', 'owl', 'xsd')."
    )


def test_undeclared_prefix_multiple_sorted():
    def raiser():
        raise UndeclaredPrefixError(frozenset({PrefixName("z"), PrefixName("a")}))

    assert _run(raiser) == (
        'Undeclared prefix(es): "a", "z". '
        "Use `set_prefix` to declare them, or use a built-in prefix "
        "('rdf', 'rdfs', 'owl', 'xsd')."
    )


def test_selection_not_found():
    def raiser():
        raise SelectionNotFoundError(SelectionName("ghosts"))

    assert _run(raiser) == (
        'Selection "ghosts" does not exist. '
        "Use `find_entities` or `match_axioms` (with `into=` set) to create one."
    )


def test_selection_exists():
    def raiser():
        raise SelectionExistsError(SelectionName("dogs"), 17)

    assert _run(raiser) == (
        'Selection "dogs" already exists (17 items). Pass mode="replace" to overwrite it.'
    )


def test_selection_kind_conflict():
    def raiser():
        raise SelectionKindConflictError(SelectionName("shared"))

    assert _run(raiser) == (
        'Selection "shared" already exists as the other kind '
        "(axiom vs entity); names are unique across both kinds. "
        "Remove it first to reuse the name."
    )


def test_selection_expr_error():
    def raiser():
        msg = "intersect needs at least two operands"
        raise SelectionExprError(msg)

    assert _run(raiser) == "Invalid set expression: intersect needs at least two operands"


def test_union_dispatch_error_with_missing_and_unknown():
    def raiser():
        raise UnionDispatchError(
            union_name="Axiom",
            closest_variant="SubClassOf",
            keys=frozenset({"sub_class"}),
            missing=frozenset({"super_class"}),
            unknown=frozenset({"oops"}),
        )

    assert _run(raiser) == (
        "Input does not match any Axiom variant. "
        'Closest variant: "SubClassOf". '
        "Missing required field(s): ['super_class']. "
        "Unknown field(s): ['oops']. "
        'Check the schema for "SubClassOf", '
        "or pick a different Axiom variant."
    )


def test_union_dispatch_error_only_missing():
    def raiser():
        raise UnionDispatchError(
            union_name="Axiom",
            closest_variant="SubClassOf",
            keys=frozenset(),
            missing=frozenset({"sub_class", "super_class"}),
            unknown=frozenset(),
        )

    assert _run(raiser) == (
        "Input does not match any Axiom variant. "
        'Closest variant: "SubClassOf". '
        "Missing required field(s): ['sub_class', 'super_class']. "
        'Check the schema for "SubClassOf", '
        "or pick a different Axiom variant."
    )


def test_ontology_not_found():
    def raiser():
        raise OntologyNotFoundError(Path("/tmp/missing.db"))

    assert _run(raiser) == (
        'Ontology "/tmp/missing.db" not found. Use `create_ontology` to create it.'
    )


def test_ontology_exists():
    def raiser():
        raise OntologyExistsError(Path("/tmp/existing.db"))

    assert _run(raiser) == '"/tmp/existing.db" already exists.'


def test_ontology_schema_error():
    def raiser():
        raise OntologySchemaError("schema version mismatch")

    assert _run(raiser) == (
        "Schema error: schema version mismatch. The database may be from an incompatible version."
    )


def test_database_open_error():
    def raiser():
        raise DatabaseOpenError(path="/tmp/bad.db", detail="file is encrypted")

    assert _run(raiser) == 'Cannot open ontology at "/tmp/bad.db": file is encrypted'


def test_store_corruption_error():
    def raiser():
        raise StoreCorruptionError("axiom abc: type mismatch", ValueError("bad"))

    assert _run(raiser) == (
        "Data integrity error: axiom abc: type mismatch. This may indicate database corruption."
    )


def test_internal_error():
    def raiser():
        raise InternalError

    assert _run(raiser) == "Internal error. Please file a bug."


# -- pydantic and stdlib arms ------------------------------------------------


class _Probe(BaseModel):
    n: int


def test_validation_error_single():
    def raiser():
        _Probe(n="not an int")  # pyright: ignore[reportArgumentType]

    msg = _run(raiser)
    assert msg.startswith("Invalid input (n): ")


def test_validation_error_multiple():
    class TwoField(BaseModel):
        a: int
        b: int

    def raiser():
        TwoField(a="x", b="y")  # pyright: ignore[reportArgumentType]

    msg = _run(raiser)
    assert msg.startswith("Invalid input:\n  - a: ")
    assert "\n  - b: " in msg


def test_file_not_found_error():
    def raiser():
        raise FileNotFoundError("[Errno 2] No such file or directory: '/x'")

    assert _run(raiser) == "[Errno 2] No such file or directory: '/x'"


def test_file_exists_error():
    def raiser():
        raise FileExistsError("[Errno 17] File exists: '/x'")

    assert _run(raiser) == "[Errno 17] File exists: '/x'"


def test_permission_error():
    def raiser():
        raise PermissionError("[Errno 13] Permission denied: '/root'")

    assert _run(raiser) == "[Errno 13] Permission denied: '/root'"


# -- safety nets -------------------------------------------------------------


class _UnknownOntoloomError(OntoloomError):
    """Subclass with no explicit arm to exercise the OntoloomError safety net."""


def test_unknown_ontoloom_subclass_falls_through_safety_net():
    def raiser():
        raise _UnknownOntoloomError("future error type")

    assert _run(raiser) == "future error type"


def test_unknown_exception_falls_through_to_generic_fallback():
    def raiser():
        msg = "bug here"
        raise RuntimeError(msg)

    assert _run(raiser) == "Internal error: RuntimeError: bug here"
