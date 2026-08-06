import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from flask import Flask, Response, flash, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from app.alerts import Alert, notify
from app.services import SnmpService
from app.store import EventStore
from monitor.detector import FailedAttemptDetector
from network.configurator import load_inventory
from network.simulator import TRAPS, make_v2c_trap, send_trap
from network.snmp_traps import parse_trap
from security.engine import DetectionEngine


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "app" / "database" / "users.db"
LOG_PATH = PROJECT_ROOT / "logs" / "login_attempts.log"
EVENT_DATABASE_PATH = PROJECT_ROOT / "app" / "database" / "events.db"
INVENTORY_PATH = PROJECT_ROOT / "config" / "devices.json"
EXAMPLE_INVENTORY_PATH = PROJECT_ROOT / "config" / "devices.example.json"
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
FAILED_DETECTOR = FailedAttemptDetector()
DETECTOR_LOCK = threading.Lock()


@contextmanager
def database_connection(path: Path = DATABASE_PATH):
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database(path: Path = DATABASE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with database_connection(path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)"
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        if "full_name" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")
        connection.execute(
            "INSERT OR IGNORE INTO users (email, password_hash, full_name) VALUES (?, ?, ?)",
            ("ced@gmail.com", generate_password_hash("12345"), "Ced Vales"),
        )
        connection.execute("UPDATE users SET full_name = ? WHERE email = ? AND full_name = ''", ("Ced Vales", "ced@gmail.com"))


def valid_email(value: str) -> bool:
    return len(value) <= 254 and EMAIL_PATTERN.fullmatch(value) is not None


def inventory_path() -> Path:
    return INVENTORY_PATH if INVENTORY_PATH.exists() else EXAMPLE_INVENTORY_PATH


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
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        EVENT_DATABASE=EVENT_DATABASE_PATH,
        USER_DATABASE=DATABASE_PATH,
        SNMP_HOST=os.environ.get("SNMP_HOST", "127.0.0.1"),
        SNMP_PORT=int(os.environ.get("SNMP_PORT", "1162")),
        SNMP_COMMUNITY=os.environ.get("SNMP_COMMUNITY", "public"),
        START_BACKGROUND_SERVICES=True,
    )
    if test_config:
        app.config.update(test_config)
    if os.environ.get("TRUST_LOCAL_PROXY") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    initialize_database(Path(app.config["USER_DATABASE"]))
    event_store = EventStore(Path(app.config["EVENT_DATABASE"]))
    event_store.initialize()
    app.extensions["event_store"] = event_store
    detection_engine = DetectionEngine(event_store)
    app.extensions["detection_engine"] = detection_engine
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.touch(exist_ok=True)
    app.jinja_env.globals["csrf_token"] = csrf_token

    snmp_service = SnmpService(
        event_store,
        app.config["SNMP_HOST"],
        app.config["SNMP_PORT"],
        app.config["SNMP_COMMUNITY"],
        PROJECT_ROOT / "logs" / "snmp_traps.jsonl",
    )
    app.extensions["snmp_service"] = snmp_service
    if app.config["START_BACKGROUND_SERVICES"] and not app.config.get("TESTING"):
        snmp_service.start()

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

        with database_connection(Path(app.config["USER_DATABASE"])) as connection:
            user = connection.execute(
                "SELECT email, password_hash, full_name FROM users WHERE email = ?", (email,)
            ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_email"] = user["email"]
            session["user_name"] = user["full_name"] or user["email"].split("@", 1)[0].capitalize()
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("dashboard"), code=303)

        try:
            record_failed_login(request.remote_addr or "127.0.0.1", email)
            ip_address = request.remote_addr or "127.0.0.1"
            event_store.add_event(ip_address, "failed_login", "warning", f"Failed login for {email}", {"email": email})
            with DETECTOR_LOCK:
                alarm, count = FAILED_DETECTOR.record(ip_address, datetime.now())
            if alarm:
                message = f"Brute-force threshold reached: {count} failed logins in 30 seconds"
                event_store.add_event(ip_address, "brute_force", "critical", message)
                notify(Alert(ip_address, "critical", message))
        except OSError:
            app.logger.exception("Unable to write authentication event")
            flash("The authentication service is temporarily unavailable.", "error")
            return redirect(url_for("login_page"), code=303)

        flash("The email or password is incorrect.", "error")
        return redirect(url_for("login_page"), code=303)

    @app.post("/register")
    def register():
        if not valid_csrf():
            flash("Your form expired. Please try again.", "error")
            return redirect(url_for("login_page", mode="register"), code=303)
        full_name = " ".join(request.form.get("full_name", "").strip().split())
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not 2 <= len(full_name) <= 80:
            flash("Enter your name using 2 to 80 characters.", "error")
            return redirect(url_for("login_page", mode="register"), code=303)
        if not valid_email(email):
            flash("Enter a valid email address.", "error")
            return redirect(url_for("login_page", mode="register"), code=303)
        if len(password) < 8:
            flash("Use at least 8 characters for your password.", "error")
            return redirect(url_for("login_page", mode="register"), code=303)
        try:
            with database_connection(Path(app.config["USER_DATABASE"])) as connection:
                connection.execute(
                    "INSERT INTO users (email, password_hash, full_name) VALUES (?, ?, ?)",
                    (email, generate_password_hash(password), full_name),
                )
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "error")
            return redirect(url_for("login_page", mode="register"), code=303)
        session.clear()
        session["user_email"] = email
        session["user_name"] = full_name
        session["csrf_token"] = secrets.token_urlsafe(32)
        event_store.add_event("account", "user_registered", "info", f"New local account created for {email}")
        return redirect(url_for("dashboard"), code=303)

    @app.get("/dashboard")
    @login_required
    def dashboard():
        try:
            devices = load_inventory(inventory_path())
        except (OSError, ValueError):
            devices = []
        return render_template(
            "dashboard.html",
            display_name=session["user_email"].split("@", 1)[0].capitalize(),
            devices=devices,
            jobs=event_store.jobs(),
            snmp_status=snmp_service.status(),
            trap_types=TRAPS,
        )

    @app.get("/api/events")
    @login_required
    def api_events():
        result = event_store.paginated_events(
            request.args.get("page", 1, type=int),
            request.args.get("per_page", 10, type=int),
            request.args.get("severity"),
        )
        return {**result, "summary": event_store.summary(), "timeline": event_store.timeline(), "snmp": snmp_service.status()}

    @app.post("/api/events/delete")
    @login_required
    def delete_events():
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        mode = request.form.get("mode", "")
        now = datetime.now(timezone.utc)
        start = end = None
        if mode == "older_hour":
            end = now - timedelta(hours=1)
        elif mode == "older_day":
            end = now - timedelta(days=1)
        elif mode == "custom":
            try:
                start = datetime.fromisoformat(request.form["start"]).replace(tzinfo=timezone.utc)
                end = datetime.fromisoformat(request.form["end"]).replace(tzinfo=timezone.utc) + timedelta(days=1, microseconds=-1)
            except (KeyError, ValueError):
                return {"error": "choose a valid start and end date"}, 400
            if start > end:
                return {"error": "start date must be before end date"}, 400
        elif mode != "all":
            return {"error": "invalid deletion range"}, 400
        deleted = event_store.delete_events(start, end)
        return {"ok": True, "deleted": deleted}

    @app.post("/api/events/<int:event_id>/status")
    @login_required
    def event_status(event_id: int):
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        if not event_store.update_status(event_id, request.form.get("status", "")):
            return {"error": "invalid event or status"}, 400
        return {"ok": True}

    @app.post("/api/simulate/trap")
    @login_required
    def simulate_trap():
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        kind = request.form.get("kind", "linkDown")
        if kind not in TRAPS:
            return {"error": "unknown trap type"}, 400
        packet = make_v2c_trap(kind, app.config["SNMP_COMMUNITY"])
        decoded = parse_trap(packet, "127.0.0.1")
        sent = send_trap("127.0.0.1", app.config["SNMP_PORT"], kind, app.config["SNMP_COMMUNITY"])
        return {
            "ok": True,
            "message": f"{kind} trap sent",
            "packet": {
                "bytes": sent,
                "hex": packet.hex(" "),
                "version": f"SNMPv{decoded.version}",
                "community": "[redacted]",
                "pdu": "Trap-PDU (0xA7)",
                "destination": f"127.0.0.1:{app.config['SNMP_PORT']}/udp",
                "trap_oid": decoded.trap_oid,
                "varbinds": decoded.varbinds,
                "severity": decoded.severity,
            },
        }

    @app.post("/api/simulate/logins")
    @login_required
    def simulate_logins():
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        source = "198.51.100.25"
        for number in range(1, 6):
            event_store.add_event(source, "failed_login", "warning", f"Simulated failed login {number}/5")
        message = "Brute-force threshold reached: 5 failed logins in 30 seconds"
        event_store.add_event(source, "brute_force", "critical", message, {"simulated": True})
        notify(Alert(source, "critical", message))
        return {"ok": True, "message": "Brute-force incident simulated"}

    @app.post("/api/simulate/login-attempt")
    @login_required
    def simulate_login_attempt():
        """Run one isolated authentication-lab attempt without changing the signed-in user."""
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with database_connection(Path(app.config["USER_DATABASE"])) as connection:
            user = connection.execute(
                "SELECT email, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["demo_attempt_times"] = []
            session["demo_event_ids"] = []
            session["demo_alerted"] = False
            event_store.add_event("authentication-lab", "login_success", "info", f"Successful demo login for {email}")
            return {"ok": True, "authenticated": True, "count": 0, "message": "Credentials accepted — demo user logged in."}

        now = time.time()
        attempts = [stamp for stamp in session.get("demo_attempt_times", []) if now - stamp < 30]
        attempts.append(now)
        attempts = attempts[-5:]
        count = len(attempts)
        session["demo_attempt_times"] = attempts
        event_id = event_store.add_event(
            "203.0.113.42",
            "failed_login",
            "warning",
            f"Authentication lab rejected attempt {count}/5",
            {"email": email or "(empty)", "username": email or "(empty)", "password_fingerprint": "interactive-guess", "simulated": True, "password_logged": False},
        )
        event_ids = [*session.get("demo_event_ids", []), event_id][-len(attempts):]
        session["demo_event_ids"] = event_ids
        triggered = count >= 5
        detection = None
        if triggered and not session.get("demo_alerted"):
            message = "Brute-force threshold reached: 5 failed logins in the interactive lab"
            alert_event_id = event_store.add_event("203.0.113.42", "brute_force", "critical", message, {"simulated": True})
            detection = detection_engine.create_incident(
                "AUTH-BRUTE-001", "203.0.113.42", message, [*event_ids, alert_event_id],
                {"threshold": 5, "window_seconds": 30, "username": email},
            )
            notify(Alert("203.0.113.42", "critical", message))
            session["demo_alerted"] = True
        return {
            "ok": True,
            "authenticated": False,
            "count": count,
            "triggered": triggered,
            "message": "Critical brute-force incident created." if triggered else f"Credentials rejected. {5 - count} attempts remain before alerting.",
            "attempts": attempts,
            "window_seconds": 30,
            "incident_id": detection.incident_id if detection else None,
        }

    @app.get("/api/simulate/login-status")
    @login_required
    def login_simulation_status():
        now = time.time()
        attempts = [stamp for stamp in session.get("demo_attempt_times", []) if now - stamp < 30]
        session["demo_attempt_times"] = attempts
        session["demo_event_ids"] = session.get("demo_event_ids", [])[-len(attempts):] if attempts else []
        if not attempts:
            session["demo_alerted"] = False
        return {
            "count": len(attempts),
            "remaining_seconds": max(0, round(30 - (now - attempts[0]), 1)) if attempts else 0,
            "ages": [round(now - stamp, 1) for stamp in attempts],
        }

    @app.post("/api/simulate/login-reset")
    @login_required
    def reset_login_simulation():
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        session["demo_attempt_times"] = []
        session["demo_event_ids"] = []
        session["demo_alerted"] = False
        return {"ok": True}

    @app.post("/api/simulate/credential-attack")
    @login_required
    def simulate_credential_attack():
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        attack_type = request.form.get("attack_type", "")
        patterns = {
            "brute_force": [("203.0.113.10", "admin", f"guess-{index}") for index in range(5)],
            "password_spray": [("203.0.113.20", user, "shared-winter-password") for user in ("admin", "finance", "support", "hr", "operations")],
            "credential_stuffing": [("203.0.113.30", f"user{index}@example.com", f"breached-pair-{index}") for index in range(5)],
            "distributed": [(f"198.51.100.{index + 10}", "administrator", f"guess-{index}") for index in range(5)],
        }
        if attack_type not in patterns:
            return {"error": "unknown credential attack type"}, 400
        event_ids = []
        evidence_rows = []
        for number, (source, username, fingerprint) in enumerate(patterns[attack_type], 1):
            metadata = {
                "username": username,
                "password_fingerprint": fingerprint,
                "password_logged": False,
                "attack_type": attack_type,
                "simulated": True,
            }
            event_ids.append(event_store.add_event(source, "authentication_failure", "warning", f"Rejected authentication attempt {number}/5 for {username}", metadata))
            evidence_rows.append({"number": number, "source": source, "username": username, "credential_pattern": fingerprint})
        detection = detection_engine.correlate_credentials(attack_type, event_ids)
        if not detection.matched:
            return {"ok": True, "matched": False, "rule_id": detection.rule_id, "events": evidence_rows}
        return {"ok": True, "matched": True, "rule_id": detection.rule_id, "incident_id": detection.incident_id, "events": evidence_rows}

    @app.post("/api/ingest/suricata")
    @login_required
    def ingest_suricata():
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        upload = request.files.get("file")
        raw = upload.read().decode("utf-8", errors="replace") if upload else request.form.get("content", "")
        if not raw.strip():
            return {"error": "provide an EVE JSON file or JSON Lines content"}, 400
        incidents = []
        imported = 0
        errors = []
        for line_number, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: {exc.msg}")
                continue
            imported += 1
            alert = record.get("alert", {})
            severity_number = int(alert.get("severity", 3))
            severity = "critical" if severity_number == 1 else "warning" if severity_number == 2 else "info"
            source = record.get("src_ip", "unknown")
            message = alert.get("signature") or f"Suricata {record.get('event_type', 'event')}"
            event_id = event_store.add_event(source, "suricata_" + record.get("event_type", "event"), severity, message, record)
            if record.get("event_type") == "alert":
                summary = f"Suricata signature {alert.get('signature_id', 'unknown')} matched: {message}"
                detection = detection_engine.create_incident("NIDS-SURI-001", source, summary, [event_id], {"eve_record": record, "line": line_number})
                if detection.incident_id:
                    incidents.append(detection.incident_id)
        return {"ok": True, "imported": imported, "incidents": incidents, "errors": errors}

    @app.post("/api/config/preview/<device_name>")
    @login_required
    def preview_config(device_name: str):
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        try:
            device = next(item for item in load_inventory(inventory_path()) if item.name == device_name)
        except (OSError, ValueError, StopIteration):
            return {"error": "device not found"}, 404
        output = "\n".join(device.commands)
        job_id = event_store.add_job(device.name, "dry-run", "previewed", list(device.commands), output)
        event_store.add_event(device.name, "config_preview", "info", f"Configuration preview created (job {job_id})")
        return {
            "ok": True,
            "job_id": job_id,
            "commands": list(device.commands),
            "device": {"name": device.name, "host": device.host, "port": device.port, "username": device.username},
            "safety_checks": [
                "Inventory schema validated",
                "Dry-run mode enforced by web UI",
                "SSH host key must exist in known_hosts",
                "Running configuration backup required before apply",
            ],
        }

    @app.post("/api/config/simulate/<device_name>")
    @login_required
    def simulate_config(device_name: str):
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        try:
            device = next(item for item in load_inventory(inventory_path()) if item.name == device_name)
        except (OSError, ValueError, StopIteration):
            return {"error": "device not found"}, 404
        outcome = request.form.get("outcome", "success")
        if outcome not in {"success", "rollback"}:
            return {"error": "invalid simulation outcome"}, 400
        if outcome == "rollback":
            status = "rolled-back"
            output = "Backup captured; validation failed; original configuration restored."
            severity = "warning"
            message = "Simulated configuration validation failed; rollback completed"
        else:
            status = "validated"
            output = "Backup captured; commands applied; post-change validation passed."
            severity = "info"
            message = "Simulated configuration change validated successfully"
        job_id = event_store.add_job(device.name, "simulation", status, list(device.commands), output)
        event_store.add_event(device.name, "config_change", severity, message, {"job_id": job_id, "simulated": True})
        transcript = [
            f"Resolved inventory target {device.name} ({device.host}:{device.port})",
            "Verified SSH host identity against known_hosts",
            f"Authenticated as {device.username} using an environment secret or SSH agent",
            f"Captured show running-config to backups/{device.name}.cfg",
            f"Entered configuration mode and staged {len(device.commands)} command(s)",
        ]
        transcript.extend(
            ["Post-change validation failed", "Restored the captured running configuration", "Closed SSH session safely"]
            if outcome == "rollback"
            else ["Post-change interface validation passed", "Saved running configuration", "Closed SSH session safely"]
        )
        return {"ok": True, "job_id": job_id, "status": status, "message": message, "transcript": transcript}

    @app.get("/incidents")
    @login_required
    def incident_list():
        return render_template("incidents.html", incidents=event_store.incidents())

    @app.get("/incidents/<int:incident_id>")
    @login_required
    def incident_detail(incident_id: int):
        incident = event_store.incident(incident_id)
        if not incident:
            return "Incident not found", 404
        return render_template("incident.html", incident=incident)

    @app.post("/api/incidents/<int:incident_id>/status")
    @login_required
    def incident_status(incident_id: int):
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        actor = session.get("user_name", session["user_email"])
        if not event_store.update_incident_status(incident_id, request.form.get("status", ""), actor):
            return {"error": "invalid incident or status"}, 400
        return {"ok": True}

    @app.post("/api/incidents/<int:incident_id>/notes")
    @login_required
    def incident_note(incident_id: int):
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        note = request.form.get("note", "").strip()
        if not note or len(note) > 2000 or not event_store.incident(incident_id):
            return {"error": "enter a note up to 2,000 characters"}, 400
        event_store.add_activity(incident_id, session.get("user_name", session["user_email"]), "Analyst note", note)
        return {"ok": True}

    @app.get("/api/evidence/<int:evidence_id>/verify")
    @login_required
    def verify_evidence(evidence_id: int):
        import hashlib

        with event_store.connect() as connection:
            evidence = connection.execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone()
        if not evidence:
            return {"error": "evidence not found"}, 404
        calculated = hashlib.sha256(evidence["content"].encode("utf-8")).hexdigest()
        return {"ok": True, "verified": hmac.compare_digest(calculated, evidence["sha256"]), "stored": evidence["sha256"], "calculated": calculated}

    @app.get("/incidents/<int:incident_id>/report")
    @login_required
    def incident_report(incident_id: int):
        incident = event_store.incident(incident_id)
        if not incident:
            return "Incident not found", 404
        if request.args.get("format") == "json":
            payload = json.dumps(incident, indent=2, sort_keys=True)
            return Response(payload, mimetype="application/json", headers={"Content-Disposition": f"attachment; filename=incident-{incident_id}.json"})
        return render_template("report.html", incident=incident)

    @app.get("/detections")
    @login_required
    def detections():
        return render_template("detections.html", rules=event_store.rules())

    @app.post("/api/detections/<rule_id>/toggle")
    @login_required
    def toggle_detection(rule_id: str):
        if not valid_csrf():
            return {"error": "invalid CSRF token"}, 400
        enabled = request.form.get("enabled") == "true"
        if not event_store.set_rule_enabled(rule_id, enabled):
            return {"error": "rule not found"}, 404
        return {"ok": True, "enabled": enabled}

    @app.post("/logout")
    @login_required
    def logout():
        if not valid_csrf():
            flash("Your form expired. Please try again.", "error")
            return redirect(url_for("dashboard"), code=303)
        session.clear()
        return redirect(url_for("login_page"), code=303)

    return app
