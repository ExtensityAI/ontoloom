"""Tests for confirmation tokens and ConfirmationRequiredError."""

import re

import pytest
from fastmcp.exceptions import ToolError
from ontoloom_mcp.components.confirmation import (
    ConfirmationRequiredError,
    confirmation_token,
)


def test_confirmation_token_is_8_lowercase_hex():
    token = confirmation_token("op", "arg1", "arg2")
    assert re.fullmatch(r"[0-9a-f]{8}", token)


def test_confirmation_token_deterministic_on_same_parts():
    a = confirmation_token("op", "x", "y")
    b = confirmation_token("op", "x", "y")
    assert a == b


def test_confirmation_token_different_parts_differ():
    a = confirmation_token("op", "x", "y")
    b = confirmation_token("op", "x", "z")
    assert a != b


def test_confirmation_token_part_boundary_matters():
    # "ab|c" vs "a|bc" must differ: parts join with "|".
    a = confirmation_token("ab", "c")
    b = confirmation_token("a", "bc")
    assert a != b


def test_confirmation_required_error_carries_token():
    err = ConfirmationRequiredError("destructive op", "deadbeef")
    assert err.token == "deadbeef"


def test_confirmation_required_error_message_includes_token():
    err = ConfirmationRequiredError("destructive op", "deadbeef")
    msg = str(err)
    assert "destructive op" in msg
    assert "deadbeef" in msg
    assert "confirm=" in msg


def test_confirmation_required_error_is_tool_error():
    err = ConfirmationRequiredError("msg", "abcd1234")
    assert isinstance(err, ToolError)


def test_confirmation_required_error_can_be_raised():
    msg = "oops"
    with pytest.raises(ConfirmationRequiredError) as exc_info:
        raise ConfirmationRequiredError(msg, "cafebabe")
    assert exc_info.value.token == "cafebabe"
