"""PrefixName typed string — lives in owl/ so query/ can depend on it without cycling."""

import re
from typing import override

from ontoloom.models import TypedStr
from ontoloom.utils import dquoted

_PREFIX_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.-]*$")


class PrefixName(TypedStr):
    """A namespace prefix label (e.g. `ex`, `rdfs`, `owl`)."""

    description = "Prefix name (e.g. 'ex', 'rdfs', 'owl')"
    pattern = r"^[a-zA-Z_][a-zA-Z0-9_.-]*$"
    examples = ("ex", "rdfs", "owl")

    @override
    @classmethod
    def parse(cls, value: str):
        if not _PREFIX_NAME_PATTERN.match(value):
            msg = (
                "PrefixName must start with a letter or underscore and contain only "
                f"letters, digits, '_', '.', '-', got {dquoted(value)}"
            )
            raise ValueError(msg)
        return value
