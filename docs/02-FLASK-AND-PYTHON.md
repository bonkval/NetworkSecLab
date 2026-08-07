# Python and Flask, Function by Function

> Scope: this lesson explains the authentication foundation inside the current application. The app factory now also registers event, simulation, configuration, detection, incident, evidence, and reporting routes; see [the learning-path overview](00-LEARNING-PATH.md) and [end-to-end flows](08-END-TO-END-FLOWS.md) for the expanded system.

This lesson explains [app/__init__.py](../app/__init__.py).

## Imports

An import makes code from another module available.

```python
import hmac
import os
import re
import secrets
import sqlite3
```

- `hmac` provides constant-time token comparison.
- `os` provides environment variables and disk synchronization.
- `re` provides regular expressions.
- `secrets` creates security-sensitive random tokens.
- `sqlite3` is Python’s built-in SQLite database driver.

```python
from datetime import datetime
from functools import wraps
from pathlib import Path
```

The `from ... import ...` form imports selected names. `Path` represents filesystem paths. `datetime` represents dates and times. `wraps` helps build a correct decorator.

Flask and Werkzeug are external packages installed by `pip`:

```python
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
```

Flask already depends on Werkzeug, which supplies lower-level web and security utilities.

## Absolute project paths

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
```

- `__file__` is the location of the current Python file.
- `Path(__file__)` converts the string into a Path object.
- `.resolve()` creates an absolute normalized path.
- The first `.parent` is `app`.
- The second `.parent` is the project root.

Using the file location is safer than assuming the terminal’s current directory.

The `/` operator joins Path objects:

```python
DATABASE_PATH = PROJECT_ROOT / "app" / "database" / "users.db"
```

It does not mean division here because `Path` defines special behavior for `/`.

## Compiling the email pattern

```python
EMAIL_PATTERN = re.compile(r"...")
```

The `r` prefix creates a raw string, so backslashes are passed to the regular-expression engine without ordinary Python escape processing.

- `^` means start of text.
- `$` means end of text.
- `[A-Za-z0-9...]` is an allowed-character set.
- `+` means one or more.
- `@` is a literal at sign.
- `(?:...)` groups without capturing.
- `\.` matches a literal dot.

This checks syntax, not whether the mailbox or domain really exists.

## `database_connection`

```python
def database_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection
```

`def` defines a function. Parentheses contain parameters; this function has none. `return` gives the created connection to the caller.

`timeout=5` allows SQLite to wait briefly if another operation holds a database lock. `row_factory = sqlite3.Row` lets query results support names such as `user["password_hash"]` instead of only numeric positions.

## `initialize_database`

```python
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
```

This ensures the database directory exists. `parents=True` creates missing ancestors. `exist_ok=True` prevents an error when it already exists.

```python
with database_connection() as connection:
```

`with` uses a context manager. For SQLite, a successful block commits the transaction; an exception rolls it back.

`CREATE TABLE IF NOT EXISTS` makes startup repeatable. Running the server again does not destroy the table.

```python
connection.execute(
    "INSERT OR IGNORE INTO users (email, password_hash) VALUES (?, ?)",
    ("ced@gmail.com", generate_password_hash("12345")),
)
```

The `?` placeholders are parameterized SQL. Values are sent separately from SQL instructions, preventing SQL injection. `INSERT OR IGNORE` does nothing if the unique email already exists.

## `valid_email`

```python
return len(value) <= 254 and EMAIL_PATTERN.fullmatch(value) is not None
```

Python evaluates `and` left to right. Both conditions must be true. `fullmatch` must match the entire string. It returns a Match object on success and `None` otherwise. `is not None` converts this into a clear Boolean condition.

## CSRF functions

`csrf_token()` creates one unpredictable token per browser session:

```python
if "csrf_token" not in session:
    session["csrf_token"] = secrets.token_urlsafe(32)
```

The token is rendered in a hidden form field. `valid_csrf()` reads the submitted token and session token, then compares them:

```python
hmac.compare_digest(submitted, expected)
```

Constant-time comparison avoids leaking partial-match timing information.

## `login_required`

This is a custom decorator that wraps protected route functions.

```python
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)
    return wrapped
```

- `view` is the original function.
- `*args` collects positional arguments.
- `**kwargs` collects named arguments.
- `@wraps(view)` preserves the original function’s name and metadata.
- An unauthenticated request is redirected.
- An authenticated request calls the original view.

## `record_failed_login`

```python
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```

`strftime` formats a datetime. `%Y` is a four-digit year, `%m` month, `%d` day, `%H` hour, `%M` minute, and `%S` second.

```python
event = f"[{timestamp}] IP: {ip_address} - EMAIL: {email} - STATUS: FAILED\n"
```

An f-string inserts values inside `{}`. `\n` ends the line.

The file opens in append mode (`"a"`), so previous entries remain. `flush()` pushes Python’s user-space buffer toward the operating system. `os.fsync()` asks the operating system to synchronize the file descriptor with storage. This adds overhead but makes the demo update immediately and reliably.

## `create_app`

This is an application factory: a function that builds an application instead of creating everything as an uncontrolled import side effect.

```python
app = Flask(__name__, template_folder="templates", static_folder="static")
```

The first argument helps Flask locate package resources. The two folder arguments state where HTML templates and static assets live.

Configuration keys include:

- `SECRET_KEY`: signs session cookies. A real deployment must use a strong environment-provided value.
- `MAX_CONTENT_LENGTH`: rejects request bodies over 16 KiB.
- `SESSION_COOKIE_HTTPONLY`: client-side JavaScript cannot read the session cookie.
- `SESSION_COOKIE_SAMESITE="Strict"`: limits cross-site cookie submission.

`test_config` allows automated tests to override settings.

`ProxyFix` is enabled only if `TRUST_LOCAL_PROXY=1`. A reverse proxy may forward the original IP and protocol, but trusting unverified forwarded headers lets clients spoof them.

## Route functions

### `login_page`

If a user is already authenticated, it redirects to the dashboard. Otherwise it renders `login.html`.

### `login`

The function performs these checks in order:

1. Validate CSRF.
2. Read and normalize email/password fields.
3. Reject malformed email without creating a log event.
4. Query the user table by email.
5. Verify the password hash.
6. Create an authenticated session on success.
7. Record a failed event on valid-looking incorrect credentials.
8. Flash a generic error and redirect.

`request.form.get("email", "")` safely returns an empty string if the field is missing. `.strip()` removes surrounding whitespace, and `.lower()` normalizes case.

The condition:

```python
if user and check_password_hash(user["password_hash"], password):
```

uses short-circuit evaluation. If `user` is `None`, Python does not call `check_password_hash`.

### `dashboard`

Two decorators apply:

```python
@app.get("/dashboard")
@login_required
```

The route is registered, but the authentication wrapper runs before the dashboard body.

### `logout`

Logout is POST because it changes authentication state. It validates CSRF, clears the session, and redirects to the login page.

## Why redirects use HTTP 303

After processing POST, the server returns a redirect instead of directly rendering a page. The browser follows it with GET. This is the Post/Redirect/Get pattern and prevents accidental form resubmission when refreshing.
