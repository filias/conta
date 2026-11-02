"""Recurring obligations of a trabalhador independente (Categoria B) in Portugal.

Each obligation has a schedule that yields (period, nominal deadline) pairs for a
calendar year. Deadlines that land on a weekend or national holiday are rolled to
the next business day.

These rules reflect the law as of 2026. Always double-check on the Portal das
Finanças / Segurança Social Direta — deadlines get changed or extended.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from .holidays import next_business_day, previous_business_day

FINANCAS = "https://www.portaldasfinancas.gov.pt"
SS_DIRETA = "https://app.seg-social.pt"
EFATURA = "https://faturas.portaldasfinancas.gov.pt"

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


class Profile(Protocol):
    social_security: bool
    vat: str  # "exempt" (art. 53.º CIVA) or "quarterly"
    eu_clients: bool
    payments_on_account: bool
    monthly_invoice: bool


Schedule = Callable[[int], list[tuple[str, date]]]


@dataclass(frozen=True)
class Obligation:
    key: str
    title: str
    category: str  # "irs", "iva", "ss" or "me" (personal routine, not a law)
    summary: str
    link: str
    schedule: Schedule
    applies_to: Callable[[Profile], bool] | None = None
    condition: str | None = None  # Human-readable form of applies_to
    personal: bool = False  # Only shown on the private side
    roll_back: bool = False  # Weekend/holiday moves it earlier, not later
    amount_label: str | None = None  # Ask for an amount when marking it done
    guide: str | None = None  # Slug of the how-to in content/guides/

    def applies(self, profile: Profile | None) -> bool:
        if profile is None:
            return not self.personal
        return self.applies_to is None or self.applies_to(profile)

    def due(self, nominal: date) -> date:
        if self.roll_back:
            return previous_business_day(nominal)
        return next_business_day(nominal)


@dataclass(frozen=True)
class Occurrence:
    obligation: Obligation
    period: str
    nominal: date
    due: date

    @property
    def key(self) -> str:
        return self.obligation.key

    @property
    def uid(self) -> str:
        return f"{self.key}/{self.period}"

    def days_left(self, today: date) -> int:
        return (self.due - today).days


def last_day(year: int, month: int) -> date:
    return date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)


def _ss_declaration(y: int) -> list[tuple[str, date]]:
    return [
        (f"Q4 {y - 1}", last_day(y, 1)),
        (f"Q1 {y}", last_day(y, 4)),
        (f"Q2 {y}", last_day(y, 7)),
        (f"Q3 {y}", last_day(y, 10)),
    ]


def _ss_payment(y: int) -> list[tuple[str, date]]:
    return [(f"{MONTHS[m - 1]} {y}", date(y, m, 20)) for m in range(1, 13)]


def _vat(day: int) -> Schedule:
    # 20th (return) / 25th (payment) of the 2nd month after the quarter, except
    # Q2, which skips August and is due in September (art. 41.º CIVA).
    def schedule(y: int) -> list[tuple[str, date]]:
        return [
            (f"Q4 {y - 1}", date(y, 2, day)),
            (f"Q1 {y}", date(y, 5, day)),
            (f"Q2 {y}", date(y, 9, day)),
            (f"Q3 {y}", date(y, 11, day)),
        ]

    return schedule


def _recapitulativa(y: int) -> list[tuple[str, date]]:
    # Quarterly filers: 20th of the month after the quarter (art. 30.º RITI) —
    # a month *before* the IVA return. The €50k switch to monthly filing only
    # counts goods, so a services-only freelancer always stays quarterly.
    return [
        (f"Q4 {y - 1}", date(y, 1, 20)),
        (f"Q1 {y}", date(y, 4, 20)),
        (f"Q2 {y}", date(y, 7, 20)),
        (f"Q3 {y}", date(y, 10, 20)),
    ]


def _monthly_invoice(y: int) -> list[tuple[str, date]]:
    return [(f"{MONTHS[m - 1]} {y}", last_day(y, m)) for m in range(1, 13)]


def _yearly(month: int, day: int, tax_year_offset: int = -1) -> Schedule:
    return lambda y: [(f"IRS {y + tax_year_offset}", date(y, month, day))]


def _payments_on_account(y: int) -> list[tuple[str, date]]:
    return [
        (f"1st {y}", date(y, 7, 20)),
        (f"2nd {y}", date(y, 9, 20)),
        (f"3rd {y}", date(y, 12, 20)),
    ]


def _pays_ss(p: Profile) -> bool:
    return p.social_security


def _vat_quarterly(p: Profile) -> bool:
    return p.vat == "quarterly"


OBLIGATIONS: list[Obligation] = [
    Obligation(
        key="invoice",
        title="Issue this month's invoice (fatura-recibo)",
        category="me",
        summary="Invoice your client on the Portal das Finanças.",
        link=FINANCAS,
        schedule=_monthly_invoice,
        applies_to=lambda p: p.monthly_invoice,
        personal=True,
        roll_back=True,
        amount_label="Invoiced",
        guide="fatura-recibo",
    ),
    Obligation(
        key="ss-declaration",
        title="Segurança Social quarterly declaration",
        category="ss",
        summary=(
            "Declare the income you invoiced in the previous quarter on Segurança "
            "Social Direta. This sets your contributions for the next 3 months."
        ),
        link=SS_DIRETA,
        schedule=_ss_declaration,
        applies_to=_pays_ss,
        condition="if you pay Segurança Social (not in your first 12 months)",
        guide="seguranca-social-declaracao-trimestral",
    ),
    Obligation(
        key="ss-payment",
        title="Segurança Social contribution payment",
        category="ss",
        summary=(
            "Pay this month's contribution, between the 10th and the 20th. "
            "The reference (referência MB) is on Segurança Social Direta."
        ),
        link=SS_DIRETA,
        schedule=_ss_payment,
        applies_to=_pays_ss,
        amount_label="Paid",
        condition="if you pay Segurança Social (not in your first 12 months)",
    ),
    Obligation(
        key="vat-return",
        title="IVA quarterly return (declaração periódica)",
        category="iva",
        summary=(
            "Submit the quarterly VAT return on the Portal das Finanças, by the "
            "20th of the second month after the quarter (Q2: September). EU "
            "services go in campo 7 and must match your declaração recapitulativa."
        ),
        link=FINANCAS,
        schedule=_vat(20),
        applies_to=_vat_quarterly,
        condition="if you're in the quarterly VAT regime (not exempt under art. 53.º)",
        amount_label="Taxable base",
    ),
    Obligation(
        key="vat-payment",
        title="IVA quarterly payment",
        category="iva",
        summary="Pay the VAT due from the quarterly return, by the 25th.",
        link=FINANCAS,
        schedule=_vat(25),
        applies_to=_vat_quarterly,
        condition="if you're in the quarterly VAT regime (not exempt under art. 53.º)",
        amount_label="Paid",
    ),
    Obligation(
        key="vat-recapitulativa",
        title="IVA declaração recapitulativa",
        category="iva",
        summary=(
            "List each EU business client's VAT number and what you invoiced them "
            "last quarter. Due a month before the IVA return — not with it. Skip "
            "it in quarters with no EU invoices."
        ),
        link=FINANCAS,
        schedule=_recapitulativa,
        applies_to=lambda p: p.eu_clients,
        condition="if you invoice business clients in other EU countries",
        guide="declaracao-recapitulativa",
    ),
    Obligation(
        key="irs-household",
        title="Confirm household (agregado familiar)",
        category="irs",
        summary=(
            "Check or update your household composition on the Portal das Finanças "
            "so deductions are attributed correctly."
        ),
        link=FINANCAS,
        schedule=_yearly(2, 15),
    ),
    Obligation(
        key="efatura",
        title="Validate invoices on e-fatura",
        category="irs",
        summary=(
            "Classify pending invoices on e-fatura, including marking which ones "
            "are expenses of your activity (afetação à atividade)."
        ),
        link=EFATURA,
        schedule=_yearly(2, 25),
    ),
    Obligation(
        key="irs-deductions",
        title="Review deductions (reclamações)",
        category="irs",
        summary=(
            "Check the deductions the AT calculated for you and complain if "
            "something's wrong, before the IRS season opens."
        ),
        link=FINANCAS,
        schedule=_yearly(3, 31),
    ),
    Obligation(
        key="irs-return",
        title="IRS annual return (Modelo 3 + Anexo B)",
        category="irs",
        summary=(
            "File last year's IRS, with Anexo B for your freelance income. "
            "The window opens on 1 April."
        ),
        link=FINANCAS,
        schedule=_yearly(6, 30),
    ),
    Obligation(
        key="irs-payment",
        title="IRS payment",
        category="irs",
        summary="Pay any IRS owed from the annual assessment (nota de cobrança).",
        link=FINANCAS,
        schedule=_yearly(8, 31),
        amount_label="Paid",
    ),
    Obligation(
        key="irs-payments-on-account",
        title="IRS payment on account (pagamento por conta)",
        category="irs",
        summary=(
            "Advance payment of this year's IRS. The AT notifies you if it "
            "applies, typically when little tax was withheld last year."
        ),
        link=FINANCAS,
        schedule=_payments_on_account,
        applies_to=lambda p: p.payments_on_account,
        amount_label="Paid",
        condition="if the AT notified you of pagamentos por conta",
    ),
]

BY_KEY = {o.key: o for o in OBLIGATIONS}


def occurrences(
    start: date, end: date, profile: Profile | None = None
) -> list[Occurrence]:
    """All occurrences whose (business-day) deadline falls within [start, end].

    With no profile, every non-personal obligation is included (the public
    calendar).
    """
    found = []
    for obligation in OBLIGATIONS:
        if not obligation.applies(profile):
            continue
        # A nominal date in late December can roll into the next January.
        for year in range(start.year - 1, end.year + 1):
            for period, nominal in obligation.schedule(year):
                due = obligation.due(nominal)
                if start <= due <= end:
                    found.append(Occurrence(obligation, period, nominal, due))
    return sorted(found, key=lambda o: (o.due, o.key))
