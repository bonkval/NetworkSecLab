# How the Local Website Runs

## Python, packages, and the virtual environment

Python includes a standard library containing modules such as `sqlite3`, `pathlib`, `threading`, and `datetime`. Flask is not part of that standard library, so it is installed as a third-party package.

```powershell
py -m venv .venv
```

`py` is the Windows Python launcher. `-m venv` runs Python’s virtual-environment module. `.venv` is the destination directory. A virtual environment gives this project its own Python executable and installed-package directory, avoiding conflicts with other projects.

```powershell
.venv\Scripts\Activate.ps1
```

Activation temporarily adjusts environment variables, especially `PATH`, so `python` and `pip` resolve to `.venv\Scripts`.

```powershell
pip install -r requirements.txt
```

`pip` is Python’s package installer. `-r` means read requirements from a file. This project declares:

```text
Flask>=3.1,<4
```

That accepts Flask 3.1 or newer while excluding the potentially incompatible major version 4. Installing Flask also installs its declared dependencies, including Werkzeug and Jinja. The project imports those libraries at runtime; it does not copy their source into your application folders.

## What “local” means

A web application still uses a client and server even when both run on one computer.

- The browser is the client.
- Flask is the HTTP server application.
- `127.0.0.1` is the loopback IP address. It always points back to the same computer.
- Port `5000` identifies the specific program receiving the connection.

When you visit `http://127.0.0.1:5000`, the browser opens a TCP connection to port 5000 on your own machine and sends an HTTP request resembling:

```http
GET / HTTP/1.1
Host: 127.0.0.1:5000
```

Flask decides which Python function handles that path, runs the function, and sends an HTTP response containing HTML. The browser parses the HTML, requests the CSS and image, calculates the layout, and draws the page.

## What happens when you run `python server.py`

Python reads [server.py](../server.py) from top to bottom:

```python
from app import create_app
```

This imports the `create_app` name from `app/__init__.py`. A directory containing `__init__.py` is a Python package, so `app` can be imported.

```python
app = create_app()
```

This calls the application factory. It builds and configures a Flask object, initializes storage, registers routes, and returns the finished application.

```python
if __name__ == "__main__":
```

Every Python module has a `__name__`. When a file is executed directly, Python sets it to `"__main__"`. When another file imports it, Python uses the module name instead. This guard prevents the development server from starting merely because a test imported `server.app`.

```python
app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
```

- `host="127.0.0.1"` accepts connections only from the same computer.
- `port=5000` selects the TCP port.
- `debug=False` disables the interactive debugger and automatic reload behavior.
- `threaded=True` lets Flask handle multiple requests in separate threads.

Flask’s built-in server is convenient for a local PoC. It is not intended to be an internet-facing production server.

## URLs, paths, and routes

These are different things:

- Filesystem path: `app/templates/login.html`
- URL path: `/login`
- Full URL: `http://127.0.0.1:5000/login`

A URL does not automatically map to a file. A Flask route maps it to a Python function:

```python
@app.post("/login")
def login():
    ...
```

The line beginning with `@` is a decorator. Flask records that POST requests for `/login` should call `login()`.

## GET and POST

`GET` asks for a representation without intending to change server state. Opening the login page uses GET.

`POST` submits data and normally changes state. Submitting credentials uses POST.

The form contains:

```html
<form action="{{ url_for('login') }}" method="post">
```

After Jinja renders it, the browser receives an action similar to `/login`. Pressing Login sends the form fields in the HTTP request body.

## Why the browser never “runs” Python

Python stays on the server side. The browser receives only the generated HTML, CSS, image, cookie headers, and status codes. It cannot see the password hash, database query, detector history, or Python functions.

The division is:

```text
Server side: Python, Flask, SQLite, filesystem logging
Client side: HTML rendering, CSS layout, built-in form validation
```

There is no custom JavaScript in this project.

## Static files versus templates

Templates contain Jinja expressions and must be rendered by Flask. Static files are returned as stored.

```text
app/templates/login.html       rendered by Jinja
app/templates/dashboard.html   rendered by Jinja
app/static/css/style.css       served directly
app/static/images/background.jpg served directly
```

Flask knows these directories because the app is created with:

```python
Flask(__name__, template_folder="templates", static_folder="static")
```

Those paths are relative to the `app` package.

## The request-response cycle

For the login page:

```text
1. Browser sends GET /
2. Flask matches @app.get("/")
3. login_page() calls render_template("login.html")
4. Jinja replaces template expressions
5. Flask returns HTML
6. Browser sees the stylesheet URL and requests it
7. CSS references background.jpg, so the browser requests the image
8. Browser renders the completed page
```

HTTP is stateless: each request is separate. Sessions and cookies provide continuity, which is explained in lesson 4.
