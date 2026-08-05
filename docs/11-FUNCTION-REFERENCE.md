# Complete Function Reference

This is a searchable inventory of every function and method defined by the project. Read the earlier lessons for deeper concepts.

## `server.py`

`server.py` defines no functions. It imports `create_app`, calls it, stores the returned Flask instance in `app`, and calls `app.run(...)` only when executed directly.

## `app/__init__.py`

### `database_connection()`

- Parameters: none.
- Returns: an open `sqlite3.Connection`.
- Side effects: opens or creates the database file.
- Called by: `initialize_database()` and `login()`.
- Important detail: configures rows so columns can be accessed by name.

### `initialize_database() -> None`

- Parameters: none.
- Returns: nothing useful.
- Side effects: creates the database directory, creates the `users` table, and inserts the demo user if absent.
- Called by: `create_app()` during startup.
- Idempotent: it can run repeatedly without creating duplicate users.

### `valid_email(value: str) -> bool`

- Parameters: candidate email string.
- Returns: `True` when length and regex checks pass, otherwise `False`.
- Side effects: none.
- Called by: `login()`.
- Limitation: validates shape, not actual domain or mailbox existence.

### `csrf_token() -> str`

- Parameters: none.
- Returns: the current session’s CSRF token.
- Side effects: creates and stores a random token if the session lacks one.
- Called by: Jinja while rendering login and dashboard forms.

### `valid_csrf() -> bool`

- Parameters: none explicitly; reads Flask’s current `request` and `session` proxies.
- Returns: whether the submitted token securely matches the session token.
- Side effects: none.
- Called by: `login()` and `logout()`.

### `login_required(view)`

- Parameters: route function to protect.
- Returns: a wrapped route function.
- Side effects: none when defined; redirects anonymous requests when invoked.
- Applied to: `dashboard()` and `logout()`.

### `wrapped(*args, **kwargs)`

- Nested inside: `login_required`.
- Parameters: forwards any positional and keyword route parameters.
- Returns: a redirect for anonymous users or the original view’s response.
- Why nested: it closes over `view`, retaining access to the protected function.

### `record_failed_login(ip_address: str, email: str) -> None`

- Parameters: client IP and normalized email.
- Returns: nothing useful.
- Side effects: appends, flushes, and synchronizes one event line.
- Called by: `login()` only after valid-looking incorrect credentials.
- Can raise: filesystem-related `OSError`, handled by the caller.

### `create_app(test_config=None) -> Flask`

- Parameters: optional configuration dictionary used mainly by tests.
- Returns: fully configured Flask application.
- Side effects: initializes database/log storage and registers routes.
- Called by: `server.py`.
- Contains: the four route functions below.

### `login_page()`

- Route: `GET /`.
- Returns: dashboard redirect for an authenticated session, otherwise rendered login HTML.

### `login()`

- Route: `POST /login`.
- Inputs: email, password, and CSRF form fields plus request IP.
- Returns: an HTTP 303 redirect.
- Side effects: may query the database, create a session, flash a message, or append a failed event.
- Security order: CSRF, input normalization, syntax validation, parameterized lookup, password-hash verification.

### `dashboard()`

- Route: `GET /dashboard`.
- Returns: rendered dashboard HTML.
- Protection: `@login_required`.
- Side effects: may create a CSRF token while rendering the logout form.

### `logout()`

- Route: `POST /logout`.
- Returns: HTTP 303 redirect.
- Side effects: clears session after CSRF validation.
- Protection: `@login_required`.

## `monitor/common.py`

### `follow(log_path: Path, stop_event, start_at_end: bool)`

- Parameters: log path, thread-safe stop Event, and startup-position choice.
- Returns: a generator that yields complete new lines one at a time.
- Side effects: opens and reads the log; prints a missing-file warning.
- Called by: viewer and detector.
- Runs until: stop Event is set.
- Recovery: reopens after disappearance or truncation.

## `monitor/detector.py`

### `FailedAttemptDetector.__init__(threshold=5, window_seconds=30)`

- Parameters: trigger count and window length.
- Returns: a new configured instance implicitly.
- Side effects: initializes empty per-IP history state.

### `FailedAttemptDetector.record(ip_address: str, event_time: datetime)`

- Parameters: event IP and parsed timestamp.
- Returns: `(alarm_required, count)` tuple.
- Side effects: appends the timestamp, removes expired entries, and clears the IP history after an alert.
- State scope: each instance has its own histories.

### `clear_terminal() -> None`

- Parameters: none.
- Returns: nothing useful.
- Side effects: runs `cls` on Windows or `clear` elsewhere.
- Called by: `trigger_alarm()`.

### `play_alarm(alarm_path: Path) -> None`

- Parameters: path to audio asset.
- Returns: nothing useful.
- Side effects: plays sound or prints a warning.
- Platform paths: `winsound` on Windows, `afplay` on macOS, `aplay` on Linux.
- Called by: an alarm thread or `--test-alarm`.

### `show_popup(ip_address: str, timestamp: datetime) -> None`

- Parameters: flagged IP and alert time.
- Returns: nothing useful.
- Side effects: opens a topmost Tkinter warning dialog.
- Failure behavior: silently returns if GUI support is unavailable.
- Called by: an optional popup thread.

### `trigger_alarm(ip_address, timestamp, alarm_path, popup) -> None`

- Parameters: alert details, audio path, and popup setting.
- Returns: nothing useful.
- Side effects: starts audio/popup threads, clears terminal, prints banner.
- Called by: `run_detector()`.

### `run_detector(log_path, alarm_path, popup, from_start) -> None`

- Parameters: runtime paths and behavior flags.
- Returns: normally only after shutdown.
- Side effects: continuously reads, parses, counts, prints, and triggers alerts.
- Owns: one `FailedAttemptDetector` instance for that process run.

### `parse_args()`

- Parameters: none explicitly; reads `sys.argv` through argparse.
- Returns: Namespace containing parsed CLI options.
- Side effects: prints help/errors and may exit for invalid arguments.

### `main() -> int`

- Parameters: none.
- Returns: process status code `0` after normal completion.
- Side effects: enables terminal handling, installs signal handlers, tests audio or starts detection.
- Called by: the module’s `__main__` guard.

## `monitor/viewer.py`

### `main() -> int`

- Parameters: none.
- Returns: process status code `0` after shutdown.
- Side effects: parses arguments, installs signal handlers, follows log, prints colored lines.
- Called by: the module’s `__main__` guard.

## Functions imported from libraries

The project calls many functions it did not define. Important examples include:

- `render_template`: loads and renders Jinja HTML.
- `redirect`: creates an HTTP redirect response.
- `url_for`: creates a URL from a Flask endpoint name.
- `flash`: stores a one-request message in the session.
- `generate_password_hash` and `check_password_hash`: create and verify password hashes.
- `re.compile` and `fullmatch`: construct and apply regex patterns.
- `sqlite3.connect`: opens SQLite.
- `datetime.now`, `strptime`, and `strftime`: create, parse, and format time.
- `Path.open`, `mkdir`, `touch`, and `resolve`: filesystem operations.
- `threading.Thread` and `threading.Event`: concurrency and shutdown signaling.
- `signal.signal`: registers operating-system signal handlers.
- `subprocess.run`: executes an external audio program on non-Windows systems.
