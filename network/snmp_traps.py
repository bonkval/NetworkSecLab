"""Small dependency-free SNMP v1/v2c trap receiver and alert logger."""

from __future__ import annotations

import argparse
import json
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


class SnmpDecodeError(ValueError):
    pass


@dataclass(frozen=True)
class TrapEvent:
    received_at: str
    source: str
    version: str
    community: str
    trap_oid: str
    severity: str
    varbinds: dict[str, str]


class BerReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def item(self) -> tuple[int, bytes]:
        if self.pos >= len(self.data):
            raise SnmpDecodeError("unexpected end of packet")
        tag = self.data[self.pos]
        self.pos += 1
        if self.pos >= len(self.data):
            raise SnmpDecodeError("missing BER length")
        length = self.data[self.pos]
        self.pos += 1
        if length & 0x80:
            count = length & 0x7F
            if not count or count > 4 or self.pos + count > len(self.data):
                raise SnmpDecodeError("invalid BER length")
            length = int.from_bytes(self.data[self.pos : self.pos + count], "big")
            self.pos += count
        end = self.pos + length
        if end > len(self.data):
            raise SnmpDecodeError("truncated BER value")
        value = self.data[self.pos:end]
        self.pos = end
        return tag, value


def decode_oid(data: bytes) -> str:
    if not data:
        raise SnmpDecodeError("empty OID")
    values = [data[0] // 40, data[0] % 40]
    current = 0
    for byte in data[1:]:
        current = (current << 7) | (byte & 0x7F)
        if not byte & 0x80:
            values.append(current)
            current = 0
    if current:
        raise SnmpDecodeError("incomplete OID")
    return ".".join(map(str, values))


def decode_value(tag: int, value: bytes) -> str:
    if tag == 0x06:
        return decode_oid(value)
    if tag in (0x02, 0x41, 0x42, 0x43, 0x46):
        return str(int.from_bytes(value, "big", signed=tag == 0x02))
    if tag == 0x40 and len(value) == 4:
        return socket.inet_ntoa(value)
    if tag == 0x05:
        return "null"
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return value.hex()


def _varbinds(data: bytes) -> dict[str, str]:
    reader = BerReader(data)
    result = {}
    while reader.pos < len(data):
        tag, pair_data = reader.item()
        if tag != 0x30:
            raise SnmpDecodeError("invalid varbind")
        pair = BerReader(pair_data)
        oid_tag, oid_data = pair.item()
        if oid_tag != 0x06:
            raise SnmpDecodeError("varbind has no OID")
        value_tag, value_data = pair.item()
        result[decode_oid(oid_data)] = decode_value(value_tag, value_data)
    return result


def parse_trap(packet: bytes, source: str) -> TrapEvent:
    outer = BerReader(packet)
    tag, message = outer.item()
    if tag != 0x30 or outer.pos != len(packet):
        raise SnmpDecodeError("packet is not one SNMP message")
    reader = BerReader(message)
    version_tag, version_data = reader.item()
    community_tag, community_data = reader.item()
    pdu_tag, pdu_data = reader.item()
    if version_tag != 0x02 or community_tag != 0x04:
        raise SnmpDecodeError("invalid SNMP header")
    version_number = int.from_bytes(version_data, "big", signed=True)
    community = community_data.decode("utf-8", errors="replace")
    pdu = BerReader(pdu_data)
    trap_oid = "unknown"
    if pdu_tag == 0xA7 and version_number == 1:  # SNMPv2c Trap-PDU
        for expected in (0x02, 0x02, 0x02):
            if pdu.item()[0] != expected:
                raise SnmpDecodeError("invalid v2c trap PDU")
        list_tag, list_data = pdu.item()
        if list_tag != 0x30:
            raise SnmpDecodeError("missing varbind list")
        varbinds = _varbinds(list_data)
        trap_oid = varbinds.get("1.3.6.1.6.3.1.1.4.1.0", "unknown")
        version = "2c"
    elif pdu_tag == 0xA4 and version_number == 0:  # SNMPv1 Trap-PDU
        enterprise_tag, enterprise = pdu.item()
        if enterprise_tag != 0x06:
            raise SnmpDecodeError("missing enterprise OID")
        for _ in range(4):
            pdu.item()
        list_tag, list_data = pdu.item()
        varbinds = _varbinds(list_data) if list_tag == 0x30 else {}
        trap_oid = decode_oid(enterprise)
        version = "1"
    else:
        raise SnmpDecodeError("only SNMP v1/v2c traps are supported")
    severity = classify_severity(trap_oid, varbinds)
    return TrapEvent(datetime.now(timezone.utc).isoformat(), source, version, community, trap_oid, severity, varbinds)


def classify_severity(trap_oid: str, varbinds: dict[str, str]) -> str:
    # Standard SNMPv2-MIB notifications whose numeric OIDs contain no readable
    # severity words.
    if trap_oid in {
        "1.3.6.1.6.3.1.1.5.3",  # linkDown
        "1.3.6.1.6.3.1.1.5.5",  # authenticationFailure
    }:
        return "critical"
    text = " ".join([trap_oid, *varbinds.values()]).lower()
    if any(word in text for word in ("critical", "fatal", "down", "failure")):
        return "critical"
    if any(word in text for word in ("warning", "degraded", "error")):
        return "warning"
    return "info"


def write_alert(event: TrapEvent, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = asdict(event)
    # Community strings are credentials in v1/v2c and must not be persisted.
    record.pop("community", None)
    with log_path.open("a", encoding="utf-8", buffering=1) as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"[{event.severity.upper()}] SNMPv{event.version} {event.source} {event.trap_oid}", flush=True)


def serve(host: str, port: int, communities: set[str], log_path: Path) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((host, port))
        print(f"SNMP trap receiver listening on udp://{host}:{port}")
        while True:
            packet, address = sock.recvfrom(65535)
            try:
                event = parse_trap(packet, address[0])
                if communities and event.community not in communities:
                    print(f"[REJECTED] trap from {address[0]} with unauthorized community")
                    continue
                write_alert(event, log_path)
            except SnmpDecodeError as exc:
                print(f"[INVALID] trap from {address[0]}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Receive SNMP v1/v2c traps")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=1162, help="UDP port (162 usually requires admin rights)")
    parser.add_argument("--community", action="append", default=[], help="allowed community; repeat as needed")
    parser.add_argument("--log", type=Path, default=Path("logs/snmp_traps.jsonl"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        serve(args.host, args.port, set(args.community), args.log)
    except KeyboardInterrupt:
        print("\nSNMP trap receiver stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
