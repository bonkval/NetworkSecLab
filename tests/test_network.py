import json
import tempfile
import unittest
from pathlib import Path

from network.configurator import load_inventory, run
from network.simulator import make_v2c_trap
from network.snmp_traps import BerReader, TrapEvent, classify_severity, decode_oid, parse_trap, write_alert


class ConfiguratorTests(unittest.TestCase):
    def test_inventory_and_dry_run_never_calls_executor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            path.write_text(json.dumps({"devices": [{
                "name": "switch-1", "host": "192.0.2.1", "username": "ops",
                "commands": ["hostname switch-1"]
            }]}), encoding="utf-8")
            devices = load_inventory(path)
            called = []
            self.assertEqual(run(devices, False, Path(directory), lambda *args: called.append(args)), 0)
            self.assertEqual(called, [])

    def test_rejects_empty_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            path.write_text(json.dumps({"devices": [{
                "name": "switch-1", "host": "192.0.2.1", "username": "ops", "commands": []
            }]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_inventory(path)


class SnmpTests(unittest.TestCase):
    def test_oid_decode(self):
        self.assertEqual(decode_oid(bytes([43, 6, 1, 2, 1, 1, 3, 0])), "1.3.6.1.2.1.1.3.0")

    def test_simulated_link_down_packet(self):
        event = parse_trap(make_v2c_trap("linkDown"), "127.0.0.1")
        self.assertEqual(event.trap_oid, "1.3.6.1.6.3.1.1.5.3")
        self.assertEqual(event.severity, "critical")

    def test_ber_rejects_truncation(self):
        with self.assertRaises(ValueError):
            BerReader(b"\x04\x05abc").item()

    def test_severity(self):
        self.assertEqual(classify_severity("1.2.3", {"1": "linkDown"}), "critical")
        self.assertEqual(classify_severity("1.3.6.1.6.3.1.1.5.3", {}), "critical")
        self.assertEqual(classify_severity("1.2.3", {"1": "temperature warning"}), "warning")

    def test_alert_log_does_not_store_community_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "traps.jsonl"
            event = TrapEvent("now", "192.0.2.1", "2c", "private-secret", "1.2.3", "info", {})
            write_alert(event, log)
            record = json.loads(log.read_text(encoding="utf-8"))
            self.assertNotIn("community", record)
            self.assertNotIn("private-secret", log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
