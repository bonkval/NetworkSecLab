import argparse
import os
import signal
import threading
from pathlib import Path

from monitor.common import DEFAULT_LOG, follow


STOP_EVENT = threading.Event()
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"


def main() -> int:
    parser = argparse.ArgumentParser(description="Live authentication event viewer")
    parser.add_argument("--from-start", action="store_true")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    args = parser.parse_args()
    if os.name == "nt":
        os.system("")
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signal_name, lambda _signum, _frame: STOP_EVENT.set())
    print(f"{CYAN}LIVE AUTHENTICATION EVENT STREAM{RESET}")
    print(f"Watching {args.log.resolve()} (Ctrl+C to stop)", flush=True)
    for line in follow(args.log.resolve(), STOP_EVENT, start_at_end=not args.from_start):
        color = RED if "STATUS: FAILED" in line else RESET
        print(f"{color}{line}{RESET}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
