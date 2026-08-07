# SQLite, Authentication, Sessions, and CSRF

> Scope: this lesson focuses on the user database and authentication boundary. The current project also has a separate event database for detections, incidents, evidence, rules, and configuration jobs.

## SQLite

SQLite stores a relational database in one local file: `app/database/users.db`. It does not require a separate database server.

The table schema is:

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
)
```

- `PRIMARY KEY` uniquely identifies a row.
- `UNIQUE` prevents duplicate emails.
- `NOT NULL` requires a value.
- `TEXT` stores strings.

## Querying a user

```python
user = connection.execute(
    "SELECT email, password_hash FROM users WHERE email = ?", (email,)
).fetchone()
```

`SELECT` reads columns. `WHERE` filters rows. `.fetchone()` returns one matching row or `None`.

The comma in `(email,)` matters: a one-item Python tuple requires a trailing comma. `(email)` is just the value inside parentheses.

Never build SQL by combining user text:

```python
# Unsafe idea; do not use
"SELECT * FROM users WHERE email = '" + email + "'"
```

Parameterized SQL treats the email as data rather than executable SQL syntax.

## Password hashing

A password hash is a one-way derived value. `generate_password_hash("12345")` creates a salted hash. Salt ensures identical passwords do not necessarily have identical stored strings.

At login:

```python
check_password_hash(stored_hash, submitted_password)
```

The submitted password is processed with information stored in the hash string, and the result is compared. The original password is not decrypted because it was never encrypted; hashing is not reversible by design.

The demo password is weak. Hashing protects stored credentials, but it cannot make a guessable password strong.

## Authentication versus authorization

- Authentication asks: “Who are you?”
- Authorization asks: “Are you allowed to access this resource?”

The login verifies identity. `@login_required` authorizes dashboard access based on session state.

## Flask sessions

Flask’s default session is stored in a signed browser cookie. The browser carries the cookie between requests. Signing prevents undetected modification, but it does not encrypt the content.

```python
session["user_email"] = user["email"]
```

Flask serializes the session, signs it using `SECRET_KEY`, and sends a `Set-Cookie` response header. On the next request, Flask validates the signature and reconstructs `session`.

Do not store passwords or large sensitive objects in this cookie.

## Why the secret key matters

If an attacker learns the secret key, they may be able to forge session data. The fallback key is acceptable only for a local demonstration. A deployed application should set an unpredictable environment variable:

```powershell
$env:PORTAL_SECRET_KEY = "a-long-random-secret"
python server.py
```

## Session rotation

On successful login:

```python
session.clear()
session["user_email"] = user["email"]
session["csrf_token"] = secrets.token_urlsafe(32)
```

Clearing previous state reduces session-fixation risk. A fresh CSRF token is created for the authenticated session.

## CSRF attacks

CSRF means Cross-Site Request Forgery. Without protection, a malicious page could make a visitor’s browser submit a request to another site where the visitor has an active session.

This project uses the synchronizer-token pattern:

1. Generate an unpredictable token.
2. Store it in the signed session.
3. Render it in the form.
4. Require the submitted value to match.

The `SameSite=Strict` cookie setting adds another layer but does not replace server-side validation.

## Generic login errors

The application returns the same message whether the email is unknown or the password is wrong:

```text
The email or password is incorrect.
```

Different messages would allow account enumeration. An attacker could learn registered email addresses without knowing their passwords.

## Why malformed emails are not logged

The browser’s `type="email"` check provides quick feedback. The Python regular expression is the authoritative check. Malformed input is treated as form noise rather than an authentication failure, so it does not increment the brute-force detector.

A valid-looking but nonexistent address does create a failed event. This is intentional: an attacker can try an account that is not in the database, and the system should not reveal whether the address exists.

## IP address behavior

`request.remote_addr` is the directly connected client IP. Local traffic normally appears as `127.0.0.1`.

Behind a reverse proxy, the direct connection may be the proxy. `ProxyFix` can trust forwarded headers, but only when `TRUST_LOCAL_PROXY=1`. Enabling it without a trusted proxy allows IP spoofing through headers.

## Security limitations

This PoC does not include account lockout, MFA, rate limiting at the HTTP layer, encrypted transport, password-reset flows, user registration, audit-log signing, centralized log storage, or a production WSGI server. Those omissions are appropriate for a local learning demo but important to state in a project explanation.
