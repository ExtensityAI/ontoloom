from typing import cast

from symai.components import MetadataTracker


def begin_tracking():
    return cast("MetadataTracker", MetadataTracker())
