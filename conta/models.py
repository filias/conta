from datetime import date, datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Session, SQLModel, create_engine, select

_engine = None


class Settings(SQLModel, table=True):
    """Single-row profile deciding which obligations apply and when to remind."""

    id: int = Field(default=1, primary_key=True)
    social_security: bool = True
    vat: str = "exempt"
    eu_clients: bool = False
    payments_on_account: bool = False
    monthly_invoice: bool = False
    reminder_days: str = "7,1,0"
    tracking_since: date = Field(default_factory=date.today)

    @property
    def lead_days(self) -> list[int]:
        days = {int(d) for d in self.reminder_days.split(",") if d.strip().isdigit()}
        return sorted(days, reverse=True)


class Completion(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("key", "period"),)

    id: int | None = Field(default=None, primary_key=True)
    key: str
    period: str
    amount: float | None = None
    done_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def init_db(url: str) -> None:
    global _engine
    _engine = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(_engine)


def session() -> Session:
    return Session(_engine)


def get_settings() -> Settings:
    with session() as s:
        settings = s.get(Settings, 1)
        if settings is None:
            settings = Settings()
            s.add(settings)
            s.commit()
            s.refresh(settings)
        return settings


def save_settings(**fields) -> Settings:
    with session() as s:
        settings = s.get(Settings, 1) or Settings()
        for name, value in fields.items():
            setattr(settings, name, value)
        s.add(settings)
        s.commit()
        s.refresh(settings)
        return settings


def completions() -> dict[str, Completion]:
    with session() as s:
        return {f"{c.key}/{c.period}": c for c in s.exec(select(Completion))}


def done_uids() -> set[str]:
    return set(completions())


def toggle_done(key: str, period: str, amount: float | None = None) -> bool:
    """Flip an occurrence between done and not done. Returns the new state."""
    with session() as s:
        existing = s.exec(
            select(Completion).where(Completion.key == key, Completion.period == period)
        ).first()
        if existing:
            s.delete(existing)
        else:
            s.add(Completion(key=key, period=period, amount=amount))
        s.commit()
        return existing is None
