from datetime import date
from types import SimpleNamespace

from conta.ics import _fold, _trigger, calendar
from conta.obligations import occurrences
from conta.reminders import compose, due_reminders


def settings(**kw):
    defaults = dict(
        social_security=True,
        vat="exempt",
        eu_clients=False,
        payments_on_account=False,
        monthly_invoice=False,
        lead_days=[7, 1, 0],
        tracking_since=date(2026, 1, 1),
    )
    return SimpleNamespace(**{**defaults, **kw})


def test_fold_keeps_lines_under_75_octets():
    folded = _fold("DESCRIPTION:" + "ção " * 60)
    assert all(len(line.encode()) <= 75 for line in folded.split("\r\n"))
    assert folded.replace("\r\n ", "") == "DESCRIPTION:" + "ção " * 60


def test_trigger_fires_at_nine():
    assert _trigger(0) == "PT9H"
    assert _trigger(1) == "-PT15H"
    assert _trigger(7) == "-PT159H"


def test_calendar_marks_done_and_drops_alarms():
    items = occurrences(date(2026, 6, 1), date(2026, 6, 30), settings())
    done = {items[0].uid}
    body = calendar(items, "test", alarm_days=[1], done=done)
    assert body.startswith("BEGIN:VCALENDAR\r\n")
    assert body.count("BEGIN:VEVENT") == len(items)
    assert body.count("BEGIN:VALARM") == len(items) - 1
    assert "SUMMARY:✓ " in body


def test_due_reminders_hits_lead_days_and_overdue():
    s = settings()
    # 20 Jul 2026 is the SS payment deadline (Monday).
    hits = due_reminders(date(2026, 7, 13), s, done=set())
    assert any(o.key == "ss-payment" and left == 7 for o, left in hits)
    # Overdue June payment shows until it's marked done
    later = due_reminders(date(2026, 7, 14), s, done=set())
    assert any(o.uid == "ss-payment/Jun 2026" for o, _ in later)
    later = due_reminders(date(2026, 7, 14), s, done={"ss-payment/Jun 2026"})
    assert not any(o.uid == "ss-payment/Jun 2026" for o, _ in later)


def test_compose():
    hits = due_reminders(date(2026, 7, 19), settings(), done=set())
    subject, body = compose(hits, "https://conta.example")
    assert subject.startswith("conta: ")
    assert "https://conta.example/app" in body
