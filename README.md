# Python Network Security Lab

Python Network Security Lab combines guarded SSH configuration previews, SNMP trap monitoring, brute-force login detection, incident management, and hardware-free simulation in one web interface.

## One-command demo

From PowerShell in the project directory:

```powershell
python start.py
```

The launcher creates `.venv`, installs dependencies only when they change, initializes both SQLite databases, starts the SNMP receiver and web server, and prints the dashboard address. Open:

```text
http://127.0.0.1:5000
```

Sign in with the lab account:

```text
Email:    ced@gmail.com
Password: 12345
```

Then launch any of the three guided labs directly in the dashboard. No managed switch is required. Events refresh automatically every two seconds.

- **Authentication lab:** submit valid credentials for a clean success path or make five invalid attempts while watching the detection threshold fill.
- **SNMP lab:** select a device condition and watch it move through device detection, trap encoding, UDP transport, decoding, classification, and storage.
- **Configuration lab:** generate a command diff, approve a simulated backup/apply/validate workflow, or deliberately demonstrate validation failure and rollback.

## What it demonstrates

- Unified real-time dashboard with filtering and a persistent light/dark theme
- Local registration and login with hashed passwords
- Twelve-hour signal-intensity field, live posture indicator, and contextual analyst brief
- Responsive event stream with wrapping columns, boundary-aware pagination, and confirmed retention-range deletion
- SNMP v1/v2c UDP trap decoding and community allow-listing
- Built-in `coldStart`, `linkDown`, `linkUp`, and authentication-failure simulations with raw BER packet inspection
- SQLite event persistence with open, acknowledged, and resolved lifecycle states
- Failed-login monitoring and an interactive five-attempt/30-second sliding-window detector
- Safe, inventory-driven SSH configuration previews
- Running-configuration backup requirement before CLI configuration changes
- Structured JSONL audit logs with SNMP credentials redacted
- Extensible console and generic webhook notifications
- Responsive UI, CSRF protection, password hashing, and secure sessions
- Unit and integration tests, GitHub Actions, Docker, and Python packaging metadata

## Interface and accessibility

The dashboard deliberately avoids a generic collection of KPI cards and chart-library defaults. Its signal field shows each of the last twelve hours as severity-weighted activity cells, while the live analyst brief converts the current event mix into a posture, signal-pressure score, and suggested next action.

The light/dark control follows the operating-system preference on first use and saves the user's selection in browser storage. Theme changes use a radial reveal when the browser supports View Transitions, with a reduced-motion-safe fallback. Lab states, hover feedback, code samples, incident controls, and event rows all have theme-specific colors rather than reusing dark surfaces in light mode.

The event stream uses fixed, wrapping columns so long messages remain inside the dashboard. Pagination always retains the first and last page and adds compact ellipses for large result sets.

## Cybersecurity investigation workflow

The **Detections** page contains local rules for classic brute force, password spraying, credential stuffing, distributed password attacks, and Suricata alerts. Rules can be enabled or disabled and show their conditions and ATT&CK mapping.

The authentication lab can generate each credential-attack pattern. The engine correlates the five raw authentication events by source, account, and non-secret credential fingerprint, then opens an incident when an enabled rule matches.

The **Incidents** page provides ATT&CK context, linked events, analyst notes, status transitions, SHA-256 evidence verification, response recommendations, printable HTML/PDF reports, and downloadable JSON reports. All reporting is local and free.

To test Suricata ingestion without installing Suricata, open **Detections** and upload `samples/suricata_eve.jsonl`. The importer accepts EVE JSON Lines, skips malformed records with an explanation, normalizes valid events, and creates incidents for alert records. Generic Suricata signatures remain marked `Unmapped` until an analyst assigns a defensible ATT&CK technique.

## Architecture

```text
Browser dashboard ──────── Flask API ───────── SQLite event store
       │                      │                         │
       ├── simulator buttons ─┤                         ├── incidents
       │                      ├── UDP SNMP receiver ───┤
       │                      ├── login detector ──────┤
       │                      └── config previews ─────┤
       └── live polling <──────── normalized events ──┘
```

The web process manages all demo services. The individual CLIs remain available for advanced or real-device use.

### Receiver status

`SNMP online · UDP 1162` means the local trap receiver successfully bound its UDP socket and is ready to accept simulated or lab-device traps. Port `1162` is the unprivileged lab alternative to the standard SNMP trap port `162`, which commonly requires elevated permissions. The status is operational—not decorative: the SNMP walkthrough sends a real localhost datagram through this receiver before the decoded event is persisted.

## Configuration

Optional environment variables:

```powershell
$env:PORTAL_SECRET_KEY = "replace-with-a-long-random-value"
$env:SNMP_PORT = "1162"
$env:SNMP_COMMUNITY = "private-lab-community"
$env:ALERT_WEBHOOK_URL = "https://your-service.example/webhook"
python start.py
```

See `.env.example` for the complete list. Environment variables are read directly; this project intentionally does not silently load secrets from committed files.

## Network configuration

The dashboard exposes safe previews only. It never applies device changes. Copy `config/devices.example.json` to the ignored `config/devices.json` file and update it when lab hardware is available.

CLI dry run:

```powershell
python -m network.configurator config/devices.json
```

Real-device application is deliberately explicit:

```powershell
$env:SWITCH_01_PASSWORD = "temporary-lab-password"
python -m network.configurator config/devices.json --apply
Remove-Item Env:SWITCH_01_PASSWORD
```

The current driver targets Cisco-style CLIs, rejects unknown SSH host keys, and requires a successful `show running-config` backup before sending changes. Always validate it against disposable lab equipment first.

## Standalone tools

Run the trap receiver independently:

```powershell
python -m network.snmp_traps --host 127.0.0.1 --port 1162 --community public
```

Send a test trap without copying raw packet bytes:

```powershell
python -m network.simulator linkDown
```

Legacy authentication event tools remain available:

```powershell
python -m monitor.viewer
python -m monitor.detector
```

## Testing and quality

Standard-library test run:

```powershell
python -m unittest discover -s tests -v
```

Coverage and lint checks:

```powershell
pip install pytest pytest-cov ruff
ruff check app monitor network tests server.py start.py
pytest --cov=app --cov=monitor --cov=network --cov-report=term-missing
```

The test suite includes a real localhost UDP integration test from the simulator through the SNMP receiver into SQLite.

## Docker

Create a `.env` from `.env.example`, set secure values, then run:

```powershell
docker compose up --build
```

The dashboard is exposed on TCP 5000 and the receiver on UDP 1162. Persistent database data uses a named volume.

## Production limitations

This remains an educational system. Before production use, add a maintained SNMPv3 receiver for authenticated and encrypted telemetry, vendor-tested configuration drivers with command-result validation and rollback, centralized secret management, TLS through a reverse proxy, user roles, retention policies, rate limiting, and an external database. SNMP v1/v2c community strings travel in plaintext even though this project does not persist them.
