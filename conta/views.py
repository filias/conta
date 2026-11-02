import hmac
from datetime import date, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from . import ics, models
from .auth import logged_in, login_required
from .guides import find_guide, load_guides
from .obligations import BY_KEY, OBLIGATIONS, occurrences

public = Blueprint("public", __name__)
private = Blueprint("private", __name__, url_prefix="/app")


def _content_dir() -> Path:
    return Path(current_app.config["CONTENT_DIR"]) / "guides"


def _private_dir() -> Path:
    return Path(current_app.config["PRIVATE_DIR"])


def _year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


# Public ----------------------------------------------------------------------


@public.route("/")
def index():
    today = date.today()
    upcoming = occurrences(today, today + timedelta(days=60))
    guides = load_guides(_content_dir(), public=True)
    return render_template("index.html", upcoming=upcoming, guides=guides, today=today)


@public.route("/calendar")
def calendar():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    if not 2000 <= year <= 2100:
        abort(404)
    items = occurrences(*_year_bounds(year))
    return render_template(
        "calendar.html",
        items=items,
        year=year,
        today=today,
        obligations=OBLIGATIONS,
    )


@public.route("/calendar/public.ics")
def public_ics():
    today = date.today()
    items = occurrences(date(today.year - 1, 1, 1), date(today.year + 1, 12, 31))
    body = ics.calendar(items, "Freelancer deadlines (PT)")
    return Response(body, mimetype="text/calendar")


@public.route("/guides")
def guides():
    public_guides = load_guides(_content_dir(), public=True)
    private_guides = (
        load_guides(_private_dir() / "guides", public=False) if logged_in() else []
    )
    return render_template(
        "guides.html", guides=public_guides, private_guides=private_guides
    )


@public.route("/guides/<slug>")
def guide(slug):
    found = find_guide(_content_dir(), slug, public=True)
    if not found:
        abort(404)
    return render_template("guide.html", guide=found)


@public.route("/calendar/<token>.ics")
def private_ics(token):
    expected = current_app.config.get("CALENDAR_TOKEN")
    if not expected or not hmac.compare_digest(token, expected):
        abort(404)
    settings = models.get_settings()
    today = date.today()
    items = occurrences(
        date(today.year - 1, 1, 1), date(today.year + 1, 12, 31), settings
    )
    body = ics.calendar(
        items, "conta", alarm_days=settings.lead_days, done=models.done_uids()
    )
    return Response(body, mimetype="text/calendar")


# Private ---------------------------------------------------------------------


@private.route("/")
@login_required
def dashboard():
    settings = models.get_settings()
    today = date.today()
    records = models.completions()
    done = set(records)
    start = max(settings.tracking_since, today - timedelta(days=365))
    items = occurrences(start, today + timedelta(days=120), settings)
    overdue = [i for i in items if i.due < today and i.uid not in done]
    upcoming = [i for i in items if i.due >= today]
    recent_done = [i for i in items if i.due < today and i.uid in done][-5:]
    year_items = occurrences(*_year_bounds(today.year), settings)
    totals = {}
    for item in year_items:
        amount = records[item.uid].amount if item.uid in records else None
        if item.obligation.amount_label and amount is not None:
            totals.setdefault(item.obligation, 0.0)
            totals[item.obligation] += amount
    token = current_app.config.get("CALENDAR_TOKEN")
    feed_url = (
        f"{current_app.config['SITE_URL']}/calendar/{token}.ics" if token else None
    )
    return render_template(
        "app/dashboard.html",
        overdue=overdue,
        upcoming=upcoming,
        recent_done=recent_done,
        done=done,
        records=records,
        totals=totals,
        today=today,
        feed_url=feed_url,
        settings=settings,
    )


@private.route("/toggle", methods=["POST"])
@login_required
def toggle():
    key, period = request.form.get("key", ""), request.form.get("period", "")
    if key not in BY_KEY or not period:
        abort(400)
    raw = request.form.get("amount", "").replace("€", "").replace(" ", "")
    # Accept both 1234.56 and the Portuguese 1.234,56
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        amount = float(raw) if raw else None
    except ValueError:
        amount = None
    models.toggle_done(key, period, amount)
    return redirect(request.form.get("back") or url_for("private.dashboard"))


@private.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        form = request.form
        try:
            tracking_since = date.fromisoformat(form.get("tracking_since", ""))
        except ValueError:
            tracking_since = date.today()
        models.save_settings(
            social_security="social_security" in form,
            vat="quarterly" if form.get("vat") == "quarterly" else "exempt",
            eu_clients="eu_clients" in form,
            payments_on_account="payments_on_account" in form,
            monthly_invoice="monthly_invoice" in form,
            reminder_days=form.get("reminder_days", "7,1,0"),
            tracking_since=tracking_since,
        )
        flash("Saved.")
        return redirect(url_for("private.settings"))
    return render_template("app/settings.html", settings=models.get_settings())


@private.route("/guides/<slug>")
@login_required
def private_guide(slug):
    found = find_guide(_private_dir() / "guides", slug, public=False)
    if not found:
        abort(404)
    return render_template("guide.html", guide=found)


@private.route("/media/<path:filename>")
@login_required
def media(filename):
    return send_from_directory(_private_dir() / "videos", filename)
