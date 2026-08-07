# Complete End-to-End Flows

## Startup

### One-command lab

```text
python start.py
  -> create .venv when missing
  -> install dependencies only when requirements change
  -> initialize user and event databases
  -> start the managed SNMP receiver on UDP 1162
  -> serve Flask through Waitress on TCP 5000
  -> print the local dashboard address
```

### Viewer and detector

Each starts its own Python process. Each opens the log independently and seeks to its current end. Neither shares Python memory with the server or with the other monitor.

## Loading the login page

```text
Browser GET /
  -> login_page()
  -> no authenticated user in session
  -> render login.html
  -> csrf_token() creates token
  -> Flask signs session cookie
  -> browser receives HTML and cookie
  -> browser requests style.css
  -> browser requests theme.js and style.css
  -> theme.js restores saved/system theme preference
  -> browser draws login form and theme control
```

## Malformed email

For ordinary users, the browser may stop submission because the field has `type="email"`. If the request is submitted anyway:

```text
POST /login
  -> CSRF valid
  -> normalize fields
  -> valid_email() returns false
  -> flash validation message
  -> HTTP 303 to /
  -> GET / renders message
  -> no database authentication query
  -> no log event
  -> detector count unchanged
```

## Valid-looking email and wrong password

```text
POST /login
  -> CSRF valid
  -> email syntax valid
  -> parameterized SQLite query
  -> no user, or password hash does not match
  -> append FAILED line
  -> flush + fsync
  -> flash generic message
  -> HTTP 303 redirect
```

At nearly the same time:

```text
viewer notices new bytes -> prints line
detector notices new bytes -> parses line -> updates IP history -> prints count
```

The communication is asynchronous. The server does not wait for either monitor.

## Fifth failure within 30 seconds

```text
detector.record()
  -> append fifth timestamp
  -> remove timestamps older than cutoff
  -> count is 5
  -> clear this IP history
  -> return (True, 5)

run_detector()
  -> call trigger_alarm()
  -> audio thread begins
  -> popup thread begins
  -> terminal clears
  -> ASCII warning prints
```

## Waiting longer than 30 seconds

The history remains in memory while idle. On the next event, the detector computes a new cutoff and removes old timestamps before counting. Therefore earlier attempts no longer contribute.

## Successful login

```text
POST /login with ced@gmail.com / 12345
  -> CSRF valid
  -> email valid
  -> SQLite row found
  -> check_password_hash returns true
  -> old session cleared
  -> authenticated email stored
  -> fresh CSRF token stored
  -> HTTP 303 to /dashboard
  -> @login_required finds user_email
  -> dashboard.html rendered
```

No failed event is written, so the viewer and detector remain unchanged.

## Direct dashboard access without login

```text
GET /dashboard
  -> login_required wrapper runs
  -> user_email missing from session
  -> redirect to /
```

Hiding a link would not be security. The server-side decorator is what enforces access.

## Dashboard refresh and signal field

```text
Browser GET /api/events?page=1&per_page=10
  -> login_required validates the session
  -> EventStore returns one page of normalized events
  -> EventStore calculates severity totals and twelve hourly buckets
  -> SnmpService reports receiver state and UDP port
  -> browser renders wrapped event rows
  -> browser renders hourly intensity cells
  -> browser derives posture, signal pressure, and next action
  -> refresh repeats every two seconds
```

`SNMP online · UDP 1162` therefore means the receiver thread has successfully bound the socket. It is not an inferred health value or decorative label.

## SNMP walkthrough

```text
POST /api/simulate/trap
  -> validate CSRF and requested trap kind
  -> encode an SNMP v2c BER packet
  -> send a real localhost UDP datagram to port 1162
  -> receiver validates the allowed community
  -> decode trap OID and varbinds
  -> classify severity
  -> persist normalized event and redacted JSONL audit record
  -> return safe packet evidence to the walkthrough
```

The community value travels in the SNMP v1/v2c packet but is omitted from stored audit output and redacted in the interface.

## Theme change

```text
User selects Light or Dark
  -> theme.js calculates the toggle's screen position
  -> set data-theme on the document root
  -> save preference in localStorage
  -> reveal the new theme radially when supported
  -> otherwise use the color-fade fallback
```

If the operating system requests reduced motion, the decorative transition is skipped.

## Logout

```text
POST /logout
  -> login_required passes
  -> CSRF token passes
  -> session.clear()
  -> redirect to /
```

The old authenticated cookie state is replaced. A later dashboard request is redirected.

## Processes and memory

The three terminals are three processes with separate memory spaces:

```text
Server process: Flask app and request sessions
Viewer process: file cursor and stop event
Detector process: file cursor, per-IP histories, alarm threads
```

Stopping the detector erases its in-memory history. Existing log lines remain on disk, but normal startup begins at the end and does not replay them.
