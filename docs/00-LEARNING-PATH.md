# Learning Path

This folder is a course about the exact application in this repository. It assumes you know only basic computer use. Read the lessons in number order and keep the project open beside them.

## What you built

You built three cooperating programs:

1. A Flask web application that displays a login form, checks a SQLite user database, creates a session after a correct login, and records meaningful failed logins.
2. A live viewer that follows the authentication log and prints each new event.
3. A detector that follows the same log, counts recent failures separately for each IP address, and raises an alarm when one IP reaches five failures in 30 seconds.

The important architectural idea is decoupling. The server does not import the detector or call an alarm function. It only appends text to a file. The monitor programs independently watch that file.

## What every project file does

| Path | Purpose |
|---|---|
| `server.py` | Small entry point that constructs and starts Flask. |
| `app/__init__.py` | Web routes, database setup, authentication, sessions, CSRF, validation, and logging. |
| `app/templates/login.html` | Server-rendered login page. |
| `app/templates/dashboard.html` | Protected welcome page and logout form. |
| `app/static/css/style.css` | All visual layout and styling. |
| `app/static/images/background.jpg` | Shared black wave image; CSS inverts it on the dashboard. |
| `app/database/users.db` | SQLite database generated at runtime. |
| `monitor/common.py` | Shared log-following generator. |
| `monitor/viewer.py` | Raw live event terminal. |
| `monitor/detector.py` | Parser, sliding-window state, alarm, popup, and CLI. |
| `monitor/__init__.py` | Marks `monitor` as an importable Python package. It is intentionally empty. |
| `assets/alarm.wav` | PCM audio played when the threshold is reached. |
| `logs/login_attempts.log` | Shared append-only event channel for the PoC. |
| `requirements.txt` | Declares the external Flask dependency. |
| `.gitignore` | Keeps generated/runtime files out of Git commits. |
| `README.md` | Quick setup and operating instructions. |

```text
Browser
   |
   | HTTP request
   v
Flask server -----> SQLite users database
   |
   | append one text line
   v
login_attempts.log
   |                    |
   v                    v
Live viewer         Detector -----> terminal alert
                                      audio alarm
                                      popup window
```

## Recommended order

1. [How the local website runs](01-LOCAL-WEB-RUNTIME.md)
2. [Python and Flask, function by function](02-FLASK-AND-PYTHON.md)
3. [HTML, Jinja, and CSS](03-FRONTEND.md)
4. [SQLite, authentication, sessions, and CSRF](04-DATABASE-AND-SECURITY.md)
5. [The file-based event pipeline](05-LOGGING-PIPELINE.md)
6. [The detector and sliding time window](06-DETECTOR-ENGINE.md)
7. [The viewer, command-line options, audio, and threads](07-TERMINAL-TOOLS.md)
8. [Complete request flows](08-END-TO-END-FLOWS.md)
9. [Debugging, exercises, and production limitations](09-PRACTICE-AND-NEXT-STEPS.md)
10. [Syntax glossary](10-SYNTAX-GLOSSARY.md)
11. [Complete function reference](11-FUNCTION-REFERENCE.md)

## How to study the code

Do not try to memorize it. For each lesson:

1. Read a small section.
2. Find the referenced code in the project.
3. Predict what will happen before running it.
4. Change one harmless value, such as a color or message.
5. run the program and observe the result.
6. Undo the experiment or commit it to a separate Git branch.

The goal is to build a mental model: input enters, code transforms it, state changes, and output appears.

## Commands used throughout

Run these from the project root:

```powershell
.venv\Scripts\Activate.ps1
python server.py
python -m monitor.viewer
python -m monitor.detector
```

Activation changes which `python` and `pip` executables PowerShell finds. It does not start the website. `python server.py` starts the website process.

## A note about the demo password

The demo credentials are intentionally easy to remember:

```text
Email: ced@gmail.com
Password: 12345
```

The database stores a password hash, not the text `12345`. Nevertheless, `12345` is a weak password and must never be used in a real application.
