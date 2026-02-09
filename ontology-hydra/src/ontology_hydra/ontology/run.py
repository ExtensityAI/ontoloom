import re
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from datetime import datetime

VALID_RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.\-]{0,256}$")


class RunMetadata(BaseModel):
    id: str  # e.g. "run_2026-01-15_12-30-45"
    title: str  # generated from intent
    intent: str
    input_files: list[str]  # file names
    created_at: datetime
    n_iterations: int
