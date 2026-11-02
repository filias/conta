"""Portuguese national holidays, used to roll deadlines to the next business day.

Tax and Social Security deadlines that fall on a weekend or holiday move to the
next business day (art. 279 Código Civil / art. 57 LGT). Municipal holidays are
not included.
"""

from datetime import date, timedelta
from functools import cache


def easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


FIXED = [
    (1, 1),  # Ano Novo
    (4, 25),  # Dia da Liberdade
    (5, 1),  # Dia do Trabalhador
    (6, 10),  # Dia de Portugal
    (8, 15),  # Assunção de Nossa Senhora
    (10, 5),  # Implantação da República
    (11, 1),  # Todos os Santos
    (12, 1),  # Restauração da Independência
    (12, 8),  # Imaculada Conceição
    (12, 25),  # Natal
]


@cache
def national_holidays(year: int) -> frozenset[date]:
    sunday = easter(year)
    movable = {
        sunday - timedelta(days=2),  # Sexta-feira Santa
        sunday,  # Páscoa
        sunday + timedelta(days=60),  # Corpo de Deus
    }
    return frozenset({date(year, m, d) for m, d in FIXED} | movable)


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in national_holidays(day.year)


def next_business_day(day: date) -> date:
    while not is_business_day(day):
        day += timedelta(days=1)
    return day


def previous_business_day(day: date) -> date:
    while not is_business_day(day):
        day -= timedelta(days=1)
    return day
