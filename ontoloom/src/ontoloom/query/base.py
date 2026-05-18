"""Base class for query classes; subclasses override `render()` and `_run()`."""

from ontoloom.connection import Session
from ontoloom.models import FrozenModel
from ontoloom.query.rendered import RenderedSql


class Query[T](FrozenModel):
    def render(self) -> RenderedSql:
        msg = f"{type(self).__name__} must override render()"
        raise NotImplementedError(msg)

    def _run(self, s: Session) -> T:
        msg = f"{type(self).__name__} must override _run()"
        raise NotImplementedError(msg)
