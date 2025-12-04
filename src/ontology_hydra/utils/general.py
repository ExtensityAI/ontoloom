from typing import cast

from symai.components import MetadataTracker


def track_usage():
    return cast("MetadataTracker", MetadataTracker())
