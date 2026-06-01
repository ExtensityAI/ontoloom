"""PrefixName typed string — lives in owl/ so query/ can depend on it without cycling."""

import re
from typing import override

from ontoloom.models import TypedStr
from ontoloom.utils import dquoted

_PREFIX_NAME_PATTERN = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_.-]*)?$")


class PrefixName(TypedStr):
    """A namespace prefix label (e.g. `ex`, `rdfs`, `owl`).

    The empty string is the default/no-prefix label used by IRIs of the form
    `:LocalName`. Like every other prefix it must be declared (via `set_prefix`)
    before such IRIs can be used.
    """

    description = (
        "Prefix name (e.g. 'ex', 'rdfs', 'owl'). The empty string is the default "
        "namespace label used by IRIs of the form ':LocalName'."
    )
    pattern = r"^([a-zA-Z_][a-zA-Z0-9_.-]*)?$"
    examples = ("ex", "rdfs", "owl")

    @override
    @classmethod
    def parse(cls, value: str):
        if not _PREFIX_NAME_PATTERN.match(value):
            msg = (
                "PrefixName must be empty or start with a letter or underscore and "
                f"contain only letters, digits, '_', '.', '-', got {dquoted(value)}"
            )
            raise ValueError(msg)
        return value
