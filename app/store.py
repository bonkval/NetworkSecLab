"""Persistent event and configuration-job storage."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
    metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS config_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    device TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    commands TEXT NOT NULL,
    output TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(id DESC);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status, severity);
CREATE TABLE IF NOT EXISTS detection_rules (
    rule_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    attack_id TEXT NOT NULL,
    tactic TEXT NOT NULL,
    technique TEXT NOT NULL,
    config TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    source TEXT NOT NULL,
    rule_id TEXT,
    attack_id TEXT NOT NULL,
    tactic TEXT NOT NULL,
    technique TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    summary TEXT NOT NULL,
    response_guidance TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incident_events (
    incident_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    PRIMARY KEY (incident_id, event_id)
);
CREATE TABLE IF NOT EXISTS incident_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incidents_updated ON incidents(updated_at DESC);
"""


class EventStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def add_event(
        self,
        source: str,
        event_type: str,
        severity: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO events (created_at, source, event_type, severity, message, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (created_at, source, event_type, severity, message, json.dumps(metadata or {}, sort_keys=True)),
            )
            return int(cursor.lastrowid)

    def event(self, event_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["metadata"] = json.loads(item["metadata"])
        return item

    def events(self, limit: int = 100, severity: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        sql = "SELECT * FROM events"
        params: list[Any] = []
        if severity in {"info", "warning", "critical"}:
            sql += " WHERE severity = ?"
            params.append(severity)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"])
            result.append(item)
        return result

    def paginated_events(self, page: int = 1, per_page: int = 10, severity: str | None = None) -> dict[str, Any]:
        page = max(1, page)
        per_page = max(1, min(per_page, 50))
        where = " WHERE severity = ?" if severity in {"info", "warning", "critical"} else ""
        params: list[Any] = [severity] if where else []
        with self.connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) count FROM events{where}", params).fetchone()["count"]
            rows = connection.execute(
                f"SELECT * FROM events{where} ORDER BY id DESC LIMIT ? OFFSET ?",
                [*params, per_page, (page - 1) * per_page],
            ).fetchall()
        events = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"])
            events.append(item)
        pages = max(1, (total + per_page - 1) // per_page)
        return {"events": events, "page": min(page, pages), "pages": pages, "total": total, "per_page": per_page}

    def timeline(self, hours: int = 12) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        start = now - timedelta(hours=hours - 1)
        buckets = {(start + timedelta(hours=index)).isoformat(): {"critical": 0, "warning": 0, "info": 0} for index in range(hours)}
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT created_at, severity FROM events WHERE created_at >= ? ORDER BY created_at",
                (start.isoformat(),),
            ).fetchall()
        for row in rows:
            stamp = datetime.fromisoformat(row["created_at"]).replace(minute=0, second=0, microsecond=0).isoformat()
            if stamp in buckets:
                buckets[stamp][row["severity"]] += 1
        return [{"time": stamp, **counts} for stamp, counts in buckets.items()]

    def delete_events(self, start: datetime | None = None, end: datetime | None = None) -> int:
        clauses = []
        params = []
        if start:
            clauses.append("created_at >= ?")
            params.append(start.astimezone(timezone.utc).isoformat())
        if end:
            clauses.append("created_at <= ?")
            params.append(end.astimezone(timezone.utc).isoformat())
        sql = "DELETE FROM events" + (" WHERE " + " AND ".join(clauses) if clauses else "")
        with self.connect() as connection:
            return connection.execute(sql, params).rowcount

    def summary(self) -> dict[str, int]:
        result = {"total": 0, "critical": 0, "warning": 0, "info": 0, "open": 0}
        with self.connect() as connection:
            for row in connection.execute("SELECT severity, COUNT(*) count FROM events GROUP BY severity"):
                result[row["severity"]] = row["count"]
                result["total"] += row["count"]
            row = connection.execute("SELECT COUNT(*) count FROM events WHERE status = 'open'").fetchone()
            result["open"] = row["count"]
        return result

    def update_status(self, event_id: int, status: str) -> bool:
        if status not in {"open", "acknowledged", "resolved"}:
            return False
        with self.connect() as connection:
            cursor = connection.execute("UPDATE events SET status = ? WHERE id = ?", (status, event_id))
            return cursor.rowcount == 1

    def add_job(self, device: str, mode: str, status: str, commands: list[str], output: str = "") -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO config_jobs (created_at, device, mode, status, commands, output) VALUES (?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), device, mode, status, json.dumps(commands), output),
            )
            return int(cursor.lastrowid)

    def jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM config_jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["commands"] = json.loads(item["commands"])
            result.append(item)
        return result

    def upsert_rule(self, rule: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO detection_rules
                (rule_id,title,description,severity,enabled,attack_id,tactic,technique,config)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(rule_id) DO UPDATE SET title=excluded.title,description=excluded.description,
                severity=excluded.severity,attack_id=excluded.attack_id,tactic=excluded.tactic,
                technique=excluded.technique,config=excluded.config""",
                (rule["rule_id"], rule["title"], rule["description"], rule["severity"], 1,
                 rule["attack_id"], rule["tactic"], rule["technique"], json.dumps(rule["config"])),
            )

    def rules(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM detection_rules ORDER BY title").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["enabled"] = bool(item["enabled"])
            item["config"] = json.loads(item["config"])
            result.append(item)
        return result

    def set_rule_enabled(self, rule_id: str, enabled: bool) -> bool:
        with self.connect() as connection:
            return connection.execute(
                "UPDATE detection_rules SET enabled = ? WHERE rule_id = ?", (int(enabled), rule_id)
            ).rowcount == 1

    def create_incident(self, rule: dict[str, Any], source: str, summary: str, event_ids: list[int], guidance: list[str]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO incidents
                (created_at,updated_at,title,severity,source,rule_id,attack_id,tactic,technique,confidence,summary,response_guidance)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (now, now, rule["title"], rule["severity"], source, rule["rule_id"], rule["attack_id"],
                 rule["tactic"], rule["technique"], rule.get("confidence", 85), summary, json.dumps(guidance)),
            )
            incident_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT OR IGNORE INTO incident_events (incident_id,event_id) VALUES (?,?)",
                [(incident_id, event_id) for event_id in event_ids],
            )
            connection.execute(
                "INSERT INTO incident_activity (incident_id,created_at,actor,action,details) VALUES (?,?,?,?,?)",
                (incident_id, now, "Detection engine", "Incident created", summary),
            )
            return incident_id

    def incidents(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT *, (SELECT COUNT(*) FROM incident_events WHERE incident_id=incidents.id) event_count FROM incidents ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def incident(self, incident_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
            if not row:
                return None
            event_rows = connection.execute(
                "SELECT events.* FROM events JOIN incident_events ON events.id=incident_events.event_id WHERE incident_events.incident_id=? ORDER BY events.id",
                (incident_id,),
            ).fetchall()
            activities = connection.execute(
                "SELECT * FROM incident_activity WHERE incident_id=? ORDER BY id", (incident_id,)
            ).fetchall()
            evidence = connection.execute("SELECT * FROM evidence WHERE incident_id=? ORDER BY id", (incident_id,)).fetchall()
        result = dict(row)
        result["response_guidance"] = json.loads(result["response_guidance"])
        result["events"] = []
        for event_row in event_rows:
            item = dict(event_row)
            item["metadata"] = json.loads(item["metadata"])
            result["events"].append(item)
        result["activity"] = [dict(item) for item in activities]
        result["evidence"] = [dict(item) for item in evidence]
        return result

    def add_activity(self, incident_id: int, actor: str, action: str, details: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO incident_activity (incident_id,created_at,actor,action,details) VALUES (?,?,?,?,?)",
                (incident_id, now, actor, action, details),
            )
            connection.execute("UPDATE incidents SET updated_at=? WHERE id=?", (now, incident_id))

    def update_incident_status(self, incident_id: int, status: str, actor: str) -> bool:
        if status not in {"open", "acknowledged", "contained", "resolved"}:
            return False
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            changed = connection.execute(
                "UPDATE incidents SET status=?,updated_at=? WHERE id=?", (status, now, incident_id)
            ).rowcount == 1
            if changed:
                connection.execute(
                    "INSERT INTO incident_activity (incident_id,created_at,actor,action,details) VALUES (?,?,?,?,?)",
                    (incident_id, now, actor, f"Status changed to {status}", "Analyst workflow action"),
                )
            return changed

    def add_evidence(self, incident_id: int, kind: str, content: str) -> dict[str, Any]:
        import hashlib

        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO evidence (incident_id,created_at,kind,content,sha256) VALUES (?,?,?,?,?)",
                (incident_id, created_at, kind, content, digest),
            )
        return {"id": int(cursor.lastrowid), "sha256": digest, "created_at": created_at}
