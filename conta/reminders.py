"""Daily deadline reminders by email and/or ntfy push.

Run once a day (see deploy/conta-remind.timer):  flask --app conta remind
"""

import os
import smtplib
import urllib.request
from datetime import date, timedelta
from email.message import EmailMessage

from .obligations import Occurrence, occurrences


def due_reminders(
    today: date, settings, done: set[str]
) -> list[tuple[Occurrence, int]]:
    """Open occurrences that are overdue or exactly N lead days away."""
    leads = settings.lead_days or [0]
    horizon = today + timedelta(days=max(leads))
    items = occurrences(settings.tracking_since, horizon, settings)
    found = []
    for item in items:
        if item.uid in done:
            continue
        left = item.days_left(today)
        if left < 0 or left in leads:
            found.append((item, left))
    return found


def _when(days_left: int) -> str:
    if days_left < 0:
        return f"OVERDUE by {-days_left} day{'s' if days_left < -1 else ''}"
    if days_left == 0:
        return "TODAY"
    return f"in {days_left} day{'s' if days_left > 1 else ''}"


def compose(reminders: list[tuple[Occurrence, int]], site_url: str) -> tuple[str, str]:
    soonest = min(left for _, left in reminders)
    count = len(reminders)
    subject = f"conta: {count} deadline{'s' if count > 1 else ''}"
    subject += " overdue" if soonest < 0 else f" — next {_when(soonest)}"
    lines = []
    for item, left in reminders:
        ob = item.obligation
        lines.append(
            f"• {ob.title} ({item.period}) — {item.due:%a %d %b}, {_when(left)}"
        )
        lines.append(f"  {ob.link}")
    lines += ["", f"Mark as done: {site_url}/app"]
    return subject, "\n".join(lines)


def send_email(subject: str, body: str) -> bool:
    host, to = os.environ.get("SMTP_HOST"), os.environ.get("MAIL_TO")
    if not host or not to:
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("MAIL_FROM") or os.environ.get("SMTP_USER") or to
    msg["To"] = to
    msg.set_content(body)
    port = int(os.environ.get("SMTP_PORT", 587))
    smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    with smtp_class(host, port, timeout=30) as smtp:
        if port != 465:
            smtp.starttls()
        if user := os.environ.get("SMTP_USER"):
            smtp.login(user, os.environ.get("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
    return True


def send_ntfy(subject: str, body: str) -> bool:
    url = os.environ.get("NTFY_URL")
    if not url:
        return False
    headers = {"Title": subject.encode("utf-8"), "Tags": "calendar"}
    if token := os.environ.get("NTFY_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body.encode(), headers=headers)
    urllib.request.urlopen(request, timeout=30).close()
    return True
