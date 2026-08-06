"""Inventory-driven SSH configuration with safe dry-run and backups."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class Device:
    name: str
    host: str
    username: str
    commands: tuple[str, ...]
    port: int = 22
    password_env: str | None = None


def load_inventory(path: Path) -> list[Device]:
    """Load and validate a JSON device inventory."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("devices") if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("inventory must contain a non-empty 'devices' list")
    devices: list[Device] = []
    names: set[str] = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"device {index} must be an object")
        name = str(row.get("name", ""))
        host = str(row.get("host", ""))
        username = str(row.get("username", ""))
        commands = row.get("commands")
        port = row.get("port", 22)
        if not NAME_PATTERN.fullmatch(name) or name in names:
            raise ValueError(f"device {index} has an invalid or duplicate name")
        if not host or not username:
            raise ValueError(f"device {name} requires host and username")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"device {name} has an invalid port")
        if not isinstance(commands, list) or not commands or not all(
            isinstance(command, str) and command.strip() for command in commands
        ):
            raise ValueError(f"device {name} requires non-empty string commands")
        names.add(name)
        devices.append(Device(name, host, username, tuple(commands), port, row.get("password_env")))
    return devices


def configure_device(device: Device, password: str, backup_dir: Path) -> None:
    """Back up the running config, then execute commands over SSH."""
    try:
        import paramiko
    except ImportError as exc:
        raise RuntimeError("Paramiko is required for --apply; install requirements.txt") from exc

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(
        device.host,
        port=device.port,
        username=device.username,
        password=password,
        look_for_keys=not bool(password),
        allow_agent=True,
        timeout=10,
    )
    try:
        _, stdout, stderr = client.exec_command("show running-config", timeout=30)
        backup = stdout.read().decode("utf-8", errors="replace")
        backup_error = stderr.read().decode("utf-8", errors="replace").strip()
        if backup_error or not backup.strip():
            raise RuntimeError(f"could not back up {device.name}: {backup_error or 'empty response'}")
        backup_dir.mkdir(parents=True, exist_ok=True)
        (backup_dir / f"{device.name}.cfg").write_text(backup, encoding="utf-8")

        shell = client.invoke_shell()
        shell.send("configure terminal\n")
        for command in device.commands:
            shell.send(command.rstrip() + "\n")
        shell.send("end\nwrite memory\n")
    finally:
        client.close()


def run(
    devices: list[Device],
    apply: bool,
    backup_dir: Path,
    executor: Callable[[Device, str, Path], None] = configure_device,
) -> int:
    failures = 0
    for device in devices:
        if not apply:
            print(f"[DRY-RUN] {device.name} ({device.host}:{device.port})")
            for command in device.commands:
                print(f"  {command}")
            continue
        password = os.environ.get(device.password_env, "") if device.password_env else ""
        if not password and device.password_env:
            password = getpass.getpass(f"Password for {device.name}: ")
        try:
            executor(device, password, backup_dir)
            print(f"[OK] {device.name} configured; backup saved")
        except Exception as exc:
            failures += 1
            print(f"[FAILED] {device.name}: {exc}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely configure network devices over SSH")
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--apply", action="store_true", help="make changes (default is dry-run)")
    parser.add_argument("--backup-dir", type=Path, default=Path("backups"))
    args = parser.parse_args()
    try:
        devices = load_inventory(args.inventory)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    return run(devices, args.apply, args.backup_dir)


if __name__ == "__main__":
    raise SystemExit(main())
