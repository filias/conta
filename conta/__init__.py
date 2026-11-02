import os
import secrets
from datetime import date, timedelta
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parent.parent


def create_app(config: dict | None = None) -> Flask:
    load_dotenv(ROOT / ".env")

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        ADMIN_PASSWORD_HASH=os.environ.get("ADMIN_PASSWORD_HASH"),
        CALENDAR_TOKEN=os.environ.get("CALENDAR_TOKEN"),
        SITE_URL=os.environ.get("SITE_URL", "https://conta.filias.dev").rstrip("/"),
        DATABASE_URL=os.environ.get("DATABASE_URL", f"sqlite:///{ROOT / 'conta.db'}"),
        CONTENT_DIR=os.environ.get("CONTENT_DIR", str(ROOT / "content")),
        PRIVATE_DIR=os.environ.get("PRIVATE_DIR", str(ROOT / "private")),
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Production serves over HTTPS; plain-HTTP local dev needs it unsecured
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
    )
    if config:
        app.config.update(config)
    if not app.config["SECRET_KEY"]:
        if app.config["ADMIN_PASSWORD_HASH"] and not app.testing:
            raise RuntimeError("SECRET_KEY must be set when login is enabled")
        app.config["SECRET_KEY"] = secrets.token_hex(32)

    from . import models
    from .auth import bp as auth_bp
    from .views import private, public

    models.init_db(app.config["DATABASE_URL"])
    app.register_blueprint(public)
    app.register_blueprint(private)
    app.register_blueprint(auth_bp)

    @app.context_processor
    def inject():
        from .auth import logged_in

        return {"logged_in": logged_in()}

    @app.template_filter("days_label")
    def days_label(due: date) -> str:
        left = (due - date.today()).days
        if left == 0:
            return "today"
        if left == 1:
            return "tomorrow"
        if left < 0:
            return f"{-left} days ago"
        return f"in {left} days"

    @app.template_filter("euros")
    def euros(value: float) -> str:
        whole, cents = f"{value:,.2f}".split(".")
        return f"€{whole.replace(',', '.')},{cents}"

    @app.cli.command("hash-password")
    def hash_password():
        """Print a hash for ADMIN_PASSWORD_HASH."""
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        click.echo(generate_password_hash(password))

    @app.cli.command("remind")
    @click.option("--dry-run", is_flag=True, help="Print instead of sending.")
    def remind(dry_run):
        """Send today's deadline reminders by email and/or ntfy."""
        from .reminders import compose, due_reminders, send_email, send_ntfy

        items = due_reminders(date.today(), models.get_settings(), models.done_uids())
        if not items:
            click.echo("Nothing due.")
            return
        subject, body = compose(items, app.config["SITE_URL"])
        if dry_run:
            click.echo(f"{subject}\n\n{body}")
            return
        channels = {"email": send_email, "ntfy": send_ntfy}
        sent = [name for name, send in channels.items() if send(subject, body)]
        if not sent:
            raise click.ClickException("No channel configured (SMTP_* or NTFY_URL).")
        click.echo(f"Sent via {', '.join(sent)}: {subject}")

    return app
