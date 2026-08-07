import json
import socket
import tempfile
import time
import unittest
from pathlib import Path

from app import create_app
from app.services import SnmpService
from app.store import EventStore
from network.simulator import send_trap


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store_path = Path(self.directory.name) / "events.db"
        self.app = create_app({
            "TESTING": True,
            "START_BACKGROUND_SERVICES": False,
            "EVENT_DATABASE": self.store_path,
            "USER_DATABASE": Path(self.directory.name) / "users.db",
            "SECRET_KEY": "test-secret",
        })
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["user_email"] = "ced@gmail.com"
            session["csrf_token"] = "test-token"

    def test_dashboard_and_event_api(self):
        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"Hello, Ced.", dashboard.data)
        self.assertIn(b"12-HOUR SIGNAL FIELD", dashboard.data)
        self.assertIn(b'id="posture-orbit"', dashboard.data)
        self.assertIn(b"js/theme.js", dashboard.data)
        response = self.client.post("/api/simulate/logins", data={"csrf_token": "test-token"})
        self.assertEqual(response.status_code, 200)
        payload = self.client.get("/api/events").get_json()
        self.assertEqual(payload["summary"]["critical"], 1)
        self.assertEqual(len(payload["events"]), 6)

    def test_acknowledge_requires_csrf(self):
        store = self.app.extensions["event_store"]
        event_id = store.add_event("test", "test", "info", "test event")
        self.assertEqual(self.client.post(f"/api/events/{event_id}/status").status_code, 400)
        response = self.client.post(
            f"/api/events/{event_id}/status",
            data={"csrf_token": "test-token", "status": "acknowledged"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(store.events()[0]["status"], "acknowledged")

    def test_configuration_preview_is_non_destructive(self):
        response = self.client.post(
            "/api/config/preview/access-switch-01", data={"csrf_token": "test-token"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("interface GigabitEthernet1/0/10", response.get_json()["commands"])

    def test_interactive_login_success_and_five_failure_threshold(self):
        success = self.client.post(
            "/api/simulate/login-attempt",
            data={"csrf_token": "test-token", "email": "ced@gmail.com", "password": "12345"},
        ).get_json()
        self.assertTrue(success["authenticated"])
        for expected_count in range(1, 6):
            response = self.client.post(
                "/api/simulate/login-attempt",
                data={"csrf_token": "test-token", "email": "ced@gmail.com", "password": "wrong"},
            ).get_json()
            self.assertEqual(response["count"], expected_count)
        self.assertTrue(response["triggered"])
        events = self.app.extensions["event_store"].events()
        self.assertEqual(events[0]["event_type"], "brute_force")
        self.assertFalse(events[1]["metadata"]["password_logged"])

    def test_login_window_prunes_attempts_after_thirty_seconds(self):
        with self.client.session_transaction() as session:
            session["demo_attempt_times"] = [time.time() - 31, time.time() - 5]
        status = self.client.get("/api/simulate/login-status").get_json()
        self.assertEqual(status["count"], 1)
        self.assertLessEqual(status["remaining_seconds"], 25.1)

    def test_configuration_success_and_rollback_simulations(self):
        for outcome in ("success", "rollback"):
            response = self.client.post(
                "/api/config/simulate/access-switch-01",
                data={"csrf_token": "test-token", "outcome": outcome},
            )
            self.assertEqual(response.status_code, 200)
        events = self.app.extensions["event_store"].events()
        self.assertEqual(events[0]["severity"], "warning")
        self.assertIn("rollback", events[0]["message"])

    def test_registration_creates_account_and_session(self):
        client = self.app.test_client()
        client.get("/")
        with client.session_transaction() as session:
            token = session["csrf_token"]
        response = client.post(
            "/register",
            data={"csrf_token": token, "full_name": "Alex Rivera", "email": "alex@example.com", "password": "strong-pass"},
        )
        self.assertEqual(response.status_code, 303)
        with client.session_transaction() as session:
            self.assertEqual(session["user_name"], "Alex Rivera")

    def test_event_pagination_and_deletion(self):
        store = self.app.extensions["event_store"]
        for number in range(13):
            store.add_event("test", "test_event", "info", f"Event {number}")
        page = self.client.get("/api/events?page=2&per_page=10").get_json()
        self.assertEqual(page["page"], 2)
        self.assertEqual(page["pages"], 2)
        self.assertEqual(len(page["events"]), 3)
        deleted = self.client.post(
            "/api/events/delete", data={"csrf_token": "test-token", "mode": "all"}
        ).get_json()
        self.assertEqual(deleted["deleted"], 13)

    def test_snmp_simulation_returns_decoded_packet_evidence(self):
        response = self.client.post(
            "/api/simulate/trap", data={"csrf_token": "test-token", "kind": "linkDown"}
        ).get_json()
        self.assertEqual(response["packet"]["trap_oid"], "1.3.6.1.6.3.1.1.5.3")
        self.assertEqual(response["packet"]["community"], "[redacted]")

    def test_all_credential_attack_patterns_create_mapped_incidents(self):
        for attack_type in ("brute_force", "password_spray", "credential_stuffing", "distributed"):
            result = self.client.post(
                "/api/simulate/credential-attack",
                data={"csrf_token": "test-token", "attack_type": attack_type},
            ).get_json()
            self.assertTrue(result["matched"])
            self.assertIsInstance(result["incident_id"], int)
        incidents = self.app.extensions["event_store"].incidents()
        self.assertEqual(len(incidents), 4)
        self.assertTrue(all(incident["attack_id"].startswith("T1110") for incident in incidents))

    def test_suricata_import_incident_evidence_and_free_reports(self):
        eve = json.dumps({
            "timestamp": "2026-01-01T00:00:00Z", "event_type": "alert",
            "src_ip": "192.0.2.50", "dest_ip": "192.0.2.80",
            "alert": {"signature_id": 210001, "signature": "LAB Suspicious HTTP request", "severity": 1},
        })
        result = self.client.post(
            "/api/ingest/suricata", data={"csrf_token": "test-token", "content": eve}
        ).get_json()
        self.assertEqual(result["imported"], 1)
        incident_id = result["incidents"][0]
        incident = self.app.extensions["event_store"].incident(incident_id)
        self.assertEqual(incident["rule_id"], "NIDS-SURI-001")
        evidence_id = incident["evidence"][0]["id"]
        self.assertTrue(self.client.get(f"/api/evidence/{evidence_id}/verify").get_json()["verified"])
        self.assertEqual(self.client.get(f"/incidents/{incident_id}/report").status_code, 200)
        report = self.client.get(f"/incidents/{incident_id}/report?format=json")
        self.assertIn("attachment", report.headers["Content-Disposition"])

    def test_incident_workflow_and_rule_toggle(self):
        result = self.client.post(
            "/api/simulate/credential-attack",
            data={"csrf_token": "test-token", "attack_type": "password_spray"},
        ).get_json()
        incident_id = result["incident_id"]
        self.assertEqual(self.client.get("/incidents").status_code, 200)
        self.assertEqual(self.client.get(f"/incidents/{incident_id}").status_code, 200)
        self.assertEqual(self.client.post(
            f"/api/incidents/{incident_id}/status",
            data={"csrf_token": "test-token", "status": "contained"},
        ).status_code, 200)
        self.assertEqual(self.client.post(
            f"/api/incidents/{incident_id}/notes",
            data={"csrf_token": "test-token", "note": "Reviewed related authentication evidence."},
        ).status_code, 200)
        toggle = self.client.post(
            "/api/detections/AUTH-SPRAY-001/toggle",
            data={"csrf_token": "test-token", "enabled": "false"},
        )
        self.assertFalse(toggle.get_json()["enabled"])

    def test_detections_page_includes_copyable_suricata_sample(self):
        page = self.client.get("/detections")
        self.assertIn(b"Try me", page.data)
        self.assertIn(b"Test IDS alert", page.data)
        self.assertIn(b"copy-eve-sample", page.data)


class SnmpServiceTests(unittest.TestCase):
    def test_udp_trap_reaches_event_store(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            store = EventStore(Path(directory) / "events.db")
            store.initialize()
            service = SnmpService(store, "127.0.0.1", port, "public", Path(directory) / "traps.jsonl")
            service.start()
            deadline = time.time() + 2
            while not service.ready and time.time() < deadline:
                time.sleep(0.01)
            self.assertTrue(service.ready)
            send_trap("127.0.0.1", port, "linkDown", "public")
            while not store.events() and time.time() < deadline:
                time.sleep(0.01)
            event = store.events()[0]
            self.assertEqual(event["event_type"], "snmp_trap")
            self.assertEqual(event["severity"], "critical")
            self.assertNotIn("public", (Path(directory) / "traps.jsonl").read_text(encoding="utf-8"))
            service.stop_event.set()
            service.thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
