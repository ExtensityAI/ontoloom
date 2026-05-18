"""Public RenderedSql value type — a rendered SQL string with its bind params."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderedSql:
    sql: str
    params: tuple[object, ...]
