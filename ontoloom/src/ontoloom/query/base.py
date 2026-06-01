"""Base class for query classes; subclasses override `render()` and `_run()`."""

from dataclasses import dataclass

from ontoloom.connection import Session
from ontoloom.models import FrozenModel


@dataclass(frozen=True, slots=True)
class RenderedSql:
    sql: str
    params: tuple[object, ...]


class Query[T](FrozenModel):
    def render(self) -> RenderedSql:
        msg = f"{type(self).__name__} must override render()"
        raise NotImplementedError(msg)

    def _run(self, s: Session) -> T:
        msg = f"{type(self).__name__} must override _run()"
        raise NotImplementedError(msg)


def append_pagination(
    sql_parts: list[str], params: list[object], limit: int | None, offset: int
) -> None:
    if limit is None:
        return

    sql_parts.append("LIMIT ?")
    params.append(limit)

    if offset > 0:
        sql_parts.append("OFFSET ?")
        params.append(offset)
