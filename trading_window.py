"""Trading-hour rules expressed in Turkey time, including DST conversion."""

from datetime import time
from zoneinfo import ZoneInfo

TURKEY = ZoneInfo("Europe/Istanbul")
ENTRY_START = time(16, 30)
ENTRY_CUTOFF = time(22, 30)


def turkey_datetime(value):
    """Convert an aware New York/Pandas timestamp to Turkey time."""
    return value.astimezone(TURKEY)


def can_open_position(value):
    current = turkey_datetime(value).time().replace(tzinfo=None)
    return ENTRY_START <= current < ENTRY_CUTOFF


def must_close_position(value):
    current = turkey_datetime(value).time().replace(tzinfo=None)
    return current >= ENTRY_CUTOFF
