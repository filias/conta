from datetime import date
from types import SimpleNamespace

from conta.holidays import easter, next_business_day
from conta.obligations import occurrences


def profile(**kw):
    defaults = dict(
        social_security=True,
        vat="exempt",
        eu_clients=False,
        payments_on_account=False,
        monthly_invoice=False,
    )
    return SimpleNamespace(**{**defaults, **kw})


def test_easter():
    assert easter(2026) == date(2026, 4, 5)
    assert easter(2027) == date(2027, 3, 28)


def test_next_business_day_skips_weekend_and_holidays():
    assert next_business_day(date(2026, 1, 31)) == date(2026, 2, 2)  # Saturday
    assert next_business_day(date(2026, 12, 25)) == date(2026, 12, 28)  # Natal, Fri
    assert next_business_day(date(2026, 4, 3)) == date(2026, 4, 6)  # Sexta-feira Santa
    assert next_business_day(date(2026, 3, 3)) == date(2026, 3, 3)


def test_public_calendar_includes_everything():
    keys = {o.key for o in occurrences(date(2026, 1, 1), date(2026, 12, 31))}
    assert {"vat-return", "irs-payments-on-account", "ss-payment"} <= keys


def test_profile_filters_obligations():
    items = occurrences(date(2026, 1, 1), date(2026, 12, 31), profile())
    keys = {o.key for o in items}
    assert "vat-return" not in keys
    assert "irs-payments-on-account" not in keys
    assert len([o for o in items if o.key == "ss-payment"]) == 12

    vat = occurrences(date(2026, 1, 1), date(2026, 12, 31), profile(vat="quarterly"))
    returns = [(o.period, o.due) for o in vat if o.key == "vat-return"]
    assert returns == [
        ("Q4 2025", date(2026, 2, 20)),
        ("Q1 2026", date(2026, 5, 20)),
        ("Q2 2026", date(2026, 9, 21)),  # Skips August; 20 Sep is a Sunday
        ("Q3 2026", date(2026, 11, 20)),
    ]


def test_personal_items_are_private_and_roll_back():
    public = occurrences(date(2026, 1, 1), date(2026, 12, 31))
    assert not any(o.key == "invoice" for o in public)
    mine = occurrences(
        date(2026, 1, 1), date(2026, 2, 28), profile(monthly_invoice=True)
    )
    invoices = [o for o in mine if o.key == "invoice"]
    # 31 Jan 2026 is a Saturday: invoice on Friday the 30th, not in February
    assert invoices[0].due == date(2026, 1, 30)
    assert invoices[0].period == "Jan 2026"


def test_rolled_deadline_is_kept_in_window():
    # SS declaration for Q4 2025 is nominally Sat 31 Jan, due Mon 2 Feb.
    items = occurrences(date(2026, 2, 1), date(2026, 2, 5), profile())
    decl = [o for o in items if o.key == "ss-declaration"]
    assert decl[0].nominal == date(2026, 1, 31)
    assert decl[0].due == date(2026, 2, 2)
