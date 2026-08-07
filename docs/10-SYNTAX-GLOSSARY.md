# Syntax Glossary

## Python

### Variables

```python
threshold = 5
```

The name refers to an object. Python determines the type at runtime.

### Type hints

```python
def play_alarm(alarm_path: Path) -> None:
```

`Path` documents the expected argument type. `-> None` says the function is not intended to return a useful value. Python does not enforce these hints by default.

### Functions

```python
def valid_email(value: str) -> bool:
    return ...
```

Indented statements belong to the function. `return` ends the call and sends a value back.

### Classes

```python
class FailedAttemptDetector:
    def __init__(self, threshold):
        self.threshold = threshold
```

A class defines a kind of object. `self` is the instance. Attributes store its state.

### Decorators

```python
@app.get("/")
def login_page():
```

A decorator receives a function and returns or registers a function. Flask route decorators register handlers.

### Context managers

```python
with path.open("a") as file:
    file.write(text)
```

The resource is cleaned up automatically when the block ends.

### Exceptions

```python
try:
    operation()
except OSError as exc:
    print(exc)
```

Exceptions represent abnormal conditions. The matching `except` block handles them.

### F-strings

```python
f"IP: {ip_address}"
```

Expressions inside braces are evaluated and inserted.

### List, tuple, dictionary, deque

```python
[1, 2]                    # mutable ordered list
(1, 2)                    # immutable tuple
{"ip": "127.0.0.1"}     # key/value dictionary
deque([time1, time2])     # efficient two-ended queue
```

### Boolean operators

- `and`: both conditions must be truthy.
- `or`: at least one must be truthy.
- `not`: reverses truthiness.
- `is None`: identity check for the special absence value.

### Imports

```python
import os
from pathlib import Path
from monitor.common import follow
```

The first imports a module. The second imports one name. The third imports across this project’s package structure.

### Generator

```python
def values():
    yield 1
    yield 2
```

A generator produces values lazily and pauses between yields.

### Lambda

```python
lambda _signum, _frame: STOP_EVENT.set()
```

A lambda is a small anonymous function. Leading underscores indicate intentionally unused parameters.

## HTML and Jinja

### Element and attributes

```html
<input id="email" name="email" required>
```

`input` is the element. `id`, `name`, and `required` are attributes.

### Semantic elements

- `<main>` is the page’s primary content.
- `<form>` groups submitted controls.
- `<label>` names a control.
- `<button>` performs an action.

### Jinja output

```jinja2
{{ message }}
```

Prints a value with HTML escaping.

### Jinja control flow

```jinja2
{% for item in items %}
    {{ item }}
{% endfor %}
```

Repeats template content.

## CSS

### Class selector

```css
.login-card { width: 380px; }
```

Selects `class="login-card"`.

### Pseudo-class

```css
button:hover { background: gray; }
```

Selects a state of an existing element.

### Pseudo-element

```css
.operations-page::before { content: ""; }
```

Creates a stylable generated box.

### Units

- `px`: CSS pixel.
- `%`: percentage relative to a relevant parent/property.
- `vh`: percentage of viewport height.
- `vw`: percentage of viewport width.
- `rem`: multiple of root font size.

### Colors

- `#ffffff`: hexadecimal RGB.
- `rgba(0, 0, 0, 0.5)`: red, green, blue, and alpha transparency.

## SQL

```sql
SELECT email FROM users WHERE email = ?
```

- `SELECT` reads data.
- `FROM` names the table.
- `WHERE` filters rows.
- `?` is a parameter placeholder supplied separately by Python.

## PowerShell commands

```powershell
.venv\Scripts\Activate.ps1
python -m monitor.detector --test-alarm
```

The first executes an activation script. The second starts Python, asks it to run a module, and supplies a Boolean command-line flag.

## HTTP vocabulary

- Request: message from client to server.
- Response: message from server to client.
- Header: metadata such as content type or cookies.
- Body: submitted form data or returned HTML.
- Route: mapping from method/path to code.
- Cookie: small browser-held value sent with matching requests.
- 200: successful response.
- 302/303: redirect response.
- 400: invalid request.
- 413: request too large.
- 500: unhandled server error.
