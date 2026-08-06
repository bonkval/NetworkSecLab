"""Background SNMP service managed by the web application."""

from __future__ import annotations

import socket
import threading
from dataclasses import asdict
from pathlib import Path

from app.alerts import Alert, notify
from app.store import EventStore
from network.snmp_traps import SnmpDecodeError, parse_trap, write_alert


class SnmpService:
    def __init__(self, store: EventStore, host: str, port: int, community: str, jsonl_path: Path):
        self.store = store
        self.host = host
        self.port = port
        self.community = community
        self.jsonl_path = jsonl_path
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.ready = False
        self.error = ""

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, name="snmp-receiver", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(0.5)
                sock.bind((self.host, self.port))
                self.ready = True
                while not self.stop_event.is_set():
                    try:
                        packet, address = sock.recvfrom(65535)
                    except socket.timeout:
                        continue
                    try:
                        event = parse_trap(packet, address[0])
                        if self.community and event.community != self.community:
                            continue
                        write_alert(event, self.jsonl_path)
                        message = f"SNMPv{event.version} trap {event.trap_oid}"
                        self.store.add_event(event.source, "snmp_trap", event.severity, message, asdict(event) | {"community": "[redacted]"})
                        notify(Alert(event.source, event.severity, message))
                    except SnmpDecodeError:
                        continue
        except OSError as exc:
            self.error = str(exc)
            self.store.add_event("snmp-service", "service_error", "warning", f"SNMP receiver unavailable: {exc}")
        finally:
            self.ready = False

    def status(self) -> dict[str, object]:
        return {"running": self.ready, "host": self.host, "port": self.port, "error": self.error}
