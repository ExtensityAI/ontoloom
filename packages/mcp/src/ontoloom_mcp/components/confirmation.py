"""Confirmation tokens for destructive MCP operations."""

import hashlib

from fastmcp.exceptions import ToolError


def confirmation_token(*parts: str):
    """Short hash binding an operation to its observable preconditions."""
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8]


class ConfirmationRequiredError(ToolError):
    def __init__(self, message: str, token: str):
        self.token = token
        super().__init__(f"{message}\n\nTo proceed, call again with confirm={token!r}.")
