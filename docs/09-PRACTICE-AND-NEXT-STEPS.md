# Debugging, Exercises, and Next Steps

> Scope: retain the authentication exercises below, then use the current dashboard labs, Suricata importer, incident workflow, and UDP integration tests for the expanded project.

## A debugging method

When something fails, identify the layer before changing code:

1. Is the process running?
2. Is the browser reaching the correct host and port?
3. Which HTTP status was returned?
4. Did Flask print an exception?
5. Was a log line written?
6. Did the viewer see it?
7. Did the regex accept it?
8. What count did the detector print?
9. Did the alarm file exist and play with `--test-alarm`?

This narrows the problem instead of randomly rewriting working pieces.

## Common problems

### Port already in use

Another server is listening on port 5000. Stop the previous terminal with Ctrl+C before starting another copy.

### Module not found

Activate `.venv`, install requirements, and run module commands from the project root.

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m monitor.detector
```

### No events appear

Confirm that the email is syntactically valid and credentials are wrong. `randomletters` is intentionally rejected without logging. Use `attacker@gmail.com`.

Start the monitors before the attempt because they normally begin at the end of the file.

### Old events immediately trigger

You probably used `--from-start`. Omit it for a fresh live demo.

### Alarm is silent

Run:

```powershell
python -m monitor.detector --test-alarm
```

Check system volume, output device, and the existence of `assets/alarm.wav`.

## Beginner exercises

1. Change the Login button text in `login.html`.
2. Change the card width from 380 px to 420 px.
3. Change an error message in `app/__init__.py`.
4. Change terminal cyan to another ANSI color.
5. Add the authenticated email under “Welcome :)” using `session["user_email"]` carefully.

After each change, predict which process must restart. Python changes require server restart. HTML/CSS are read per request by the development setup, though browser caching can require a hard refresh. Monitor Python changes require monitor restart.

## Intermediate exercises

1. Add a successful-login event with `STATUS: SUCCESS`, but make the detector ignore it.
2. Add a `--threshold` command-line argument and pass it into `FailedAttemptDetector`.
3. Add a `--window` argument.
4. Write automated tests for attempts from two IP addresses.
5. Mask the email in logs, such as `a******r@gmail.com`.
6. Add log rotation when the file exceeds a chosen size.

## Tests worth writing

- Malformed email produces no event.
- Valid unknown email produces one event.
- Wrong password produces one event.
- Correct password produces no failed event.
- Dashboard rejects an anonymous client.
- Logout clears authentication.
- Missing or incorrect CSRF tokens are rejected.
- Five attempts in 30 seconds trigger.
- Attempts older than 30 seconds expire.
- Different IPs are counted separately.
- An alert resets only its IP.
- Malformed log lines do not crash the monitor.

## Project explanation

Be accurate about what the project demonstrates:

> I built a local, decoupled authentication-monitoring PoC. A Flask application authenticates a hashed SQLite user, validates requests, and appends structured failed-login events. Independent processes tail the file, visualize events, and apply a per-IP sliding-window detector that triggers terminal, desktop, and audio alerts.

Avoid calling it a production SIEM or intrusion-prevention system. It is a focused demonstration of web authentication, local event pipelines, stream parsing, and threshold detection.

## What production would add

- A production WSGI server such as Waitress on Windows or Gunicorn on Linux
- HTTPS termination
- Strong secret management
- Database migrations
- Strong passwords and MFA
- Server-side rate limiting
- Structured JSON logs
- Log rotation and retention policies
- Centralized append-only event storage
- Clock normalization with UTC
- Background queues or event brokers
- Automated unit and integration tests
- Dependency pinning and vulnerability scanning
- Observability and health endpoints
- Least-privilege filesystem permissions
- A real identity provider instead of a demo account

## A suggested rebuild challenge

The best way to convert generated code into your own knowledge is to rebuild a smaller version without copying:

1. Create a Flask page with one form.
2. Print submitted values safely.
3. Add SQLite with one hashed user.
4. Add session-protected content.
5. Write failed attempts to a file.
6. Write a separate program that follows the file.
7. Add a simple count.
8. Replace the count with the sliding window.
9. Add the alarm last.

If you can explain why each step exists and diagnose it when broken, the project is no longer “vibe coded”; it has become something you understand.
