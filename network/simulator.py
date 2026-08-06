"""Generate safe local SNMP events for demos and automated tests."""

from __future__ import annotations

import argparse
import socket


TRAPS = {
    "coldStart": (1, 3, 6, 1, 6, 3, 1, 1, 5, 1),
    "linkDown": (1, 3, 6, 1, 6, 3, 1, 1, 5, 3),
    "linkUp": (1, 3, 6, 1, 6, 3, 1, 1, 5, 4),
    "authenticationFailure": (1, 3, 6, 1, 6, 3, 1, 1, 5, 5),
}


def tlv(tag: int, data: bytes) -> bytes:
    if len(data) >= 128:
        raise ValueError("simulator values must use short BER lengths")
    return bytes((tag, len(data))) + data


def encode_oid(values: tuple[int, ...]) -> bytes:
    encoded = bytearray((40 * values[0] + values[1],))
    for number in values[2:]:
        stack = [number & 0x7F]
        number >>= 7
        while number:
            stack.append(0x80 | (number & 0x7F))
            number >>= 7
        encoded.extend(reversed(stack))
    return tlv(0x06, bytes(encoded))


def varbind(name: tuple[int, ...], value: bytes) -> bytes:
    return tlv(0x30, encode_oid(name) + value)


def make_v2c_trap(kind: str = "linkDown", community: str = "public") -> bytes:
    trap_oid = TRAPS[kind]
    uptime = varbind((1, 3, 6, 1, 2, 1, 1, 3, 0), tlv(0x43, (123456).to_bytes(3, "big")))
    identity = varbind((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), encode_oid(trap_oid))
    pdu = tlv(0xA7, tlv(2, b"\x01") + tlv(2, b"\x00") + tlv(2, b"\x00") + tlv(0x30, uptime + identity))
    return tlv(0x30, tlv(2, b"\x01") + tlv(4, community.encode("utf-8")) + pdu)


def send_trap(host: str, port: int, kind: str, community: str) -> int:
    packet = make_v2c_trap(kind, community)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        return sock.sendto(packet, (host, port))


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a safe local SNMPv2c demo trap")
    parser.add_argument("kind", choices=TRAPS, nargs="?", default="linkDown")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1162)
    parser.add_argument("--community", default="public")
    args = parser.parse_args()
    size = send_trap(args.host, args.port, args.kind, args.community)
    print(f"Sent {size}-byte {args.kind} trap to udp://{args.host}:{args.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
