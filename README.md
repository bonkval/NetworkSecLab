# Local login security demo

This local PoC keeps the portal and monitor decoupled through `logs/login_attempts.log`. Passwords are never written to the audit log. Malformed email addresses are rejected without creating security events.

New to the project? Start with the detailed course in [`docs/00-LEARNING-PATH.md`](docs/00-LEARNING-PATH.md).

## Setup

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Use three PowerShell windows from the project root:

```powershell
python server.py
python -m monitor.viewer
python -m monitor.detector
```

Open `http://127.0.0.1:5000`. Arrange the browser on the left half, the viewer terminal in the upper-right quarter, and the detector terminal in the lower-right quarter. Both monitors begin at the current end of the log, so start them before submitting the five failed attempts.

The demo account is `ced@gmail.com` with password `12345`. A correct login opens the protected welcome page. Five failed requests from the same IP within 30 seconds play `assets/alarm.wav`, clear the detector terminal, render the alert banner, and open a warning dialog.

Test the sound before recording with `python -m monitor.detector --test-alarm`. Use `--no-popup` to disable the dialog or `--from-start` to intentionally replay existing log entries.

For a public deployment, replace the demo secret via `PORTAL_SECRET_KEY`, place Flask behind a production WSGI server, terminate TLS at a trusted reverse proxy, and set `TRUST_LOCAL_PROXY=1` only when that proxy is controlled by you. This PoC uses one intentionally weak demo account and must not be connected to a real identity system.
