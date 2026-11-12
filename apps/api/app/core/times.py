"""Paraguay's wall-clock times (SH-FIX-01).

Organizers think in Asunción time ("Saturday 14:00"). These helpers turn that into an
aware UTC datetime with the IANA zone America/Asuncion, so no fixed offset is ever
hard-coded and a future rule change in Paraguay is picked up from tzdata.
"""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

ASUNCION = ZoneInfo("America/Asuncion")
# What organizers type: date and time, no zone ("2026-11-14T14:00").
LOCAL_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"


def from_asuncion(text):
    """'YYYY-MM-DDTHH:MM' in Asunción -> aware UTC datetime. ValueError if malformed."""
    if not re.fullmatch(LOCAL_PATTERN, text or ""):
        raise ValueError("Use YYYY-MM-DDTHH:MM")
    return datetime.fromisoformat(text).replace(tzinfo=ASUNCION).astimezone(UTC)


def to_asuncion(value):
    """Aware datetime -> 'YYYY-MM-DDTHH:MM' in Asunción (for messages and forms)."""
    return value.astimezone(ASUNCION).strftime("%Y-%m-%dT%H:%M") if value else None
