# Complete End-to-End Flows

## Startup

### Web server

```text
python server.py
  -> import create_app
  -> create Flask object
  -> create database directory/table if missing
  -> insert demo user if missing
  -> create log directory/file if missing
  -> register routes
  -> listen on 127.0.0.1:5000
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
  -> browser requests background.jpg
  -> browser draws login form
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
