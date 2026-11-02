"""Single-user password login.

The password hash lives in ADMIN_PASSWORD_HASH (generate it with
`flask --app conta hash-password`). Failed logins are throttled per IP, which
assumes a single gunicorn worker process (see deploy/conta.service).
"""

import time
from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

bp = Blueprint("auth", __name__)

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
_failures: dict[str, list[float]] = {}


def logged_in() -> bool:
    return session.get("user") == "admin"


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not logged_in():
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def _client_ip() -> str:
    # Caddy sets X-Forwarded-For; gunicorn only listens on localhost.
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[
        0
    ]


def _recent_failures(ip: str) -> list[float]:
    cutoff = time.time() - WINDOW_SECONDS
    recent = [t for t in _failures.get(ip, []) if t > cutoff]
    _failures[ip] = recent
    return recent


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        ip = _client_ip()
        if len(_recent_failures(ip)) >= MAX_FAILURES:
            abort(429)
        password_hash = current_app.config.get("ADMIN_PASSWORD_HASH")
        password = request.form.get("password", "")
        if password_hash and check_password_hash(password_hash, password):
            _failures.pop(ip, None)
            session.clear()
            session.permanent = True
            session["user"] = "admin"
            target = request.args.get("next", "")
            # Only allow local redirects
            if not target.startswith("/") or target.startswith("//"):
                target = url_for("private.dashboard")
            return redirect(target)
        _failures.setdefault(ip, []).append(time.time())
        error = "Wrong password."
    return render_template("login.html", error=error)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("public.index"))
