import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path

from monitor.common import DEFAULT_LOG, PROJECT_ROOT, follow


DEFAULT_ALARM = PROJECT_ROOT / "assets" / "alarm.wav"
THRESHOLD = 5
WINDOW_SECONDS = 30
EVENT_PATTERN = re.compile(
    r"^\[(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] "
    r"IP: (?P<ip>[^\s]+) - EMAIL: (?P<email>[^\s]+) - STATUS: FAILED$"
)
STOP_EVENT = threading.Event()
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"


class FailedAttemptDetector:
    def __init__(self, threshold=THRESHOLD, window_seconds=WINDOW_SECONDS):
        self.threshold = threshold
        self.window = timedelta(seconds=window_seconds)
        self.histories = defaultdict(deque)

    def record(self, ip_address: str, event_time: datetime):
        history = self.histories[ip_address]
        history.append(event_time)
        cutoff = event_time - self.window
        while history and history[0] < cutoff:
            history.popleft()
        count = len(history)
        if count >= self.threshold:
            history.clear()
            return True, count
        return False, count


def clear_terminal() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def play_alarm(alarm_path: Path) -> None:
    if not alarm_path.is_file():
        print(f"{YELLOW}Audio warning: {alarm_path} was not found.{RESET}", file=sys.stderr)
        return
    try:
        if os.name == "nt":
            import winsound

            winsound.PlaySound(str(alarm_path), winsound.SND_FILENAME)
            return
        command = "afplay" if sys.platform == "darwin" else "aplay"
        executable = shutil.which(command)
        if not executable:
            raise RuntimeError(f"{command} is not installed")
        subprocess.run([executable, str(alarm_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except (OSError, RuntimeError) as exc:
        print(f"{YELLOW}Audio warning: {exc}{RESET}", file=sys.stderr)


def show_popup(ip_address: str, timestamp: datetime) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showwarning(
            "Security Alert",
            f"Potential brute-force attack detected.\n\nIP: {ip_address}\nTime: {timestamp:%Y-%m-%d %H:%M:%S}",
            parent=root,
        )
        root.destroy()
    except Exception:
        return


def trigger_alarm(ip_address: str, timestamp: datetime, alarm_path: Path, popup: bool) -> None:
    threading.Thread(target=play_alarm, args=(alarm_path,), daemon=True).start()
    if popup:
        threading.Thread(target=show_popup, args=(ip_address, timestamp), daemon=True).start()
    clear_terminal()
    border = "=" * 70
    print(f"{RED}+{border}+")
    print("|       [SECURITY ALERT] BRUTE-FORCE DETECTED - ALARM TRIGGERED       |")
    print(f"+{border}+")
    print(f"| FLAGGED IP : {ip_address:<57}|")
    print(f"| DETECTED AT: {timestamp:%Y-%m-%d %H:%M:%S}{' ' * 38}|")
    print(f"+{border}+{RESET}", flush=True)


def run_detector(log_path: Path, alarm_path: Path, popup: bool, from_start: bool) -> None:
    detector = FailedAttemptDetector()
    print(f"{CYAN}Defense monitor armed | threshold={THRESHOLD} | window={WINDOW_SECONDS}s{RESET}")
    print(f"Watching {log_path} (Ctrl+C to stop)", flush=True)
    for line in follow(log_path, STOP_EVENT, start_at_end=not from_start):
        match = EVENT_PATTERN.fullmatch(line)
        if not match:
            print(f"{YELLOW}Skipped malformed event: {line}{RESET}")
            continue
        event_time = datetime.strptime(match.group("timestamp"), "%Y-%m-%d %H:%M:%S")
        ip_address = match.group("ip")
        alarm, count = detector.record(ip_address, event_time)
        print(f"{CYAN}[LIVE]{RESET} {line} ({count}/{THRESHOLD})", flush=True)
        if alarm:
            trigger_alarm(ip_address, event_time, alarm_path, popup)


def parse_args():
    parser = argparse.ArgumentParser(description="Brute-force detector")
    parser.add_argument("--from-start", action="store_true")
    parser.add_argument("--no-popup", action="store_true")
    parser.add_argument("--test-alarm", action="store_true")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--alarm", type=Path, default=DEFAULT_ALARM)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name == "nt":
        os.system("")
    if args.test_alarm:
        print(f"Testing alarm: {args.alarm.resolve()}")
        play_alarm(args.alarm.resolve())
        return 0
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signal_name, lambda _signum, _frame: STOP_EVENT.set())
    run_detector(args.log.resolve(), args.alarm.resolve(), not args.no_popup, args.from_start)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
