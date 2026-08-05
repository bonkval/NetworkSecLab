import os
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG = PROJECT_ROOT / "logs" / "login_attempts.log"
POLL_INTERVAL = 0.05


def follow(log_path: Path, stop_event, start_at_end: bool):
    warned = False
    while not stop_event.is_set():
        try:
            with log_path.open("r", encoding="utf-8", errors="replace") as log_file:
                warned = False
                if start_at_end:
                    log_file.seek(0, os.SEEK_END)
                while not stop_event.is_set():
                    position = log_file.tell()
                    line = log_file.readline()
                    if line:
                        yield line.rstrip("\r\n")
                        continue
                    try:
                        if log_path.stat().st_size < position:
                            break
                    except FileNotFoundError:
                        break
                    stop_event.wait(POLL_INTERVAL)
        except (FileNotFoundError, PermissionError, OSError) as exc:
            if not warned:
                print(f"Waiting for log file: {exc}")
                warned = True
            stop_event.wait(0.5)
