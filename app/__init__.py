import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "app" / "database" / "users.db"
LOG_PATH = PROJECT_ROOT / "logs" / "login_attempts.log"
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


def database_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database_connection() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT OR IGNORE INTO users (email, password_hash) VALUES (?, ?)",
            ("ced@gmail.com", generate_password_hash("12345")),
        )


def valid_email(value: str) -> bool:
    return len(value) <= 254 and EMAIL_PATTERN.fullmatch(value) is not None


def csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def valid_csrf() -> bool:
    submitted = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    return bool(submitted and expected and hmac.compare_digest(submitted, expected))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)

    return wrapped


def record_failed_login(ip_address: str, email: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event = f"[{timestamp}] IP: {ip_address} - EMAIL: {email} - STATUS: FAILED\n"
    with LOG_PATH.open("a", encoding="utf-8", buffering=1) as log_file:
        log_file.write(event)
        log_file.flush()
        os.fsync(log_file.fileno())


def create_app(test_config=None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        SECRET_KEY=os.environ.get("PORTAL_SECRET_KEY", "local-demo-only-change-me"),
        MAX_CONTENT_LENGTH=16 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
    )
    if test_config:
        app.config.update(test_config)
    if os.environ.get("TRUST_LOCAL_PROXY") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    initialize_database()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.touch(exist_ok=True)
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.get("/")
    def login_page():
        if "user_email" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.post("/login")
    def login():
        if not valid_csrf():
            flash("Your form expired. Please try again.", "error")
            return redirect(url_for("login_page"), code=303)

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not valid_email(email):
            flash("Enter a valid email address.", "error")
            return redirect(url_for("login_page"), code=303)

        with database_connection() as connection:
            user = connection.execute(
                "SELECT email, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_email"] = user["email"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("dashboard"), code=303)

        try:
            record_failed_login(request.remote_addr or "127.0.0.1", email)
        except OSError:
            app.logger.exception("Unable to write authentication event")
            flash("The authentication service is temporarily unavailable.", "error")
            return redirect(url_for("login_page"), code=303)

        flash("The email or password is incorrect.", "error")
        return redirect(url_for("login_page"), code=303)

    @app.get("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    @app.post("/logout")
    @login_required
    def logout():
        if not valid_csrf():
            flash("Your form expired. Please try again.", "error")
            return redirect(url_for("dashboard"), code=303)
        session.clear()
        return redirect(url_for("login_page"), code=303)

    return app
