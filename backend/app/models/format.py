from enum import Enum


class VideoFormat(str, Enum):
    """Format registry keys. Drives prompt selection and Remotion composition."""

    SHORT_HOOK = "short_hook"
    LIST = "list"
    AUTHOR_RANKING = "author_ranking"
    SERIES_EPISODE = "series_episode"
    DEEP_DIVE = "deep_dive"
    RECAP = "recap"
    MONTHLY_REPORT = "monthly_report"
