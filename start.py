"""One-command bootstrap and launcher for the Network Security Lab."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
STAMP = VENV / ".netguard-requirements"


def requirement_hash() -> str:
    return hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest()


def main() -> int:
    if not PYTHON.exists():
        print("Creating local Python environment…")
        venv.create(VENV, with_pip=True)
    digest = requirement_hash()
    if not STAMP.exists() or STAMP.read_text(encoding="utf-8") != digest:
        print("Installing project dependencies…")
        subprocess.run([str(PYTHON), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
        STAMP.write_text(digest, encoding="utf-8")
    print("Starting Network Security Lab at http://127.0.0.1:5000")
    return subprocess.call([str(PYTHON), str(ROOT / "server.py")], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
