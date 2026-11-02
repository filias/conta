"""Minimal iCalendar (RFC 5545) feed of obligation deadlines.

Subscribe to it from Apple Calendar, Google Calendar, Thunderbird, etc. Note that
Google Calendar ignores alarms in subscribed feeds; Apple Calendar honours them.
"""

from datetime import datetime, timedelta, timezone

from .obligations import Occurrence

REMINDER_HOUR = 9  # Alarms fire at 09:00 local time, N days before


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold to at most 75 octets per line (continuations start with a space)."""
    parts, current = [], ""
    for char in line:
        if len((current + char).encode()) > 74:
            parts.append(current)
            current = " " + char
        else:
            current += char
    parts.append(current)
    return "\r\n".join(parts)


def _trigger(days_before: int) -> str:
    hours = days_before * 24 - REMINDER_HOUR
    return f"-PT{hours}H" if hours > 0 else f"PT{-hours}H"


def calendar(
    items: list[Occurrence],
    name: str,
    alarm_days: list[int] = (),
    done: set[str] = frozenset(),
) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//conta.filias.dev//conta//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        "X-WR-TIMEZONE:Europe/Lisbon",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
    ]
    for item in items:
        ob = item.obligation
        is_done = item.uid in done
        summary = f"{'✓ ' if is_done else ''}{ob.title} ({item.period})"
        description = f"{ob.summary}\n\n{ob.link}"
        if ob.condition:
            description = f"Only {ob.condition}.\n\n{description}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{item.key}-{item.period.replace(' ', '-')}@conta.filias.dev",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{item.due:%Y%m%d}",
            f"DTEND;VALUE=DATE:{item.due + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_escape(summary)}",
            f"DESCRIPTION:{_escape(description)}",
            f"URL:{ob.link}",
            f"CATEGORIES:{ob.category.upper()}",
            "TRANSP:TRANSPARENT",
        ]
        if not is_done:
            for days in alarm_days:
                lines += [
                    "BEGIN:VALARM",
                    "ACTION:DISPLAY",
                    f"DESCRIPTION:{_escape(summary)}",
                    f"TRIGGER:{_trigger(days)}",
                    "END:VALARM",
                ]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
