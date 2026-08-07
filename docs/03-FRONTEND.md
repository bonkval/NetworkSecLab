# HTML, Jinja, and CSS

## HTML describes structure

HTML uses elements such as `<form>`, `<input>`, and `<button>`. An opening tag begins an element and a closing tag ends it.

```html
<label for="email">Email</label>
<input id="email" name="email" type="email" required>
```

- `id` uniquely identifies the input in the page.
- `for="email"` connects the label to that ID for accessibility.
- `name="email"` becomes the key Flask reads from `request.form`.
- `type="email"` enables browser-level email checks.
- `required` prevents empty submission in normal browser use.

Browser validation improves usability, but an attacker can bypass it. That is why Python repeats validation on the server.

## The document skeleton

`<!doctype html>` selects modern HTML behavior. `<html lang="en">` tells assistive tools the language. The `<head>` contains metadata; `<body>` contains visible content.

```html
<meta name="viewport" content="width=device-width, initial-scale=1">
```

This makes CSS layout use the device width on mobile screens.

## Jinja template syntax

Jinja executes on the server before HTML reaches the browser.

- `{{ expression }}` prints a value.
- `{% statement %}` performs control flow.

```html
{{ url_for('static', filename='css/style.css') }}
```

`url_for` asks Flask to construct the correct URL. Hardcoding `/static/...` could break if application mounting changes.

The flash-message block is:

```jinja2
{% with messages = get_flashed_messages(with_categories=true) %}
    {% for category, message in messages %}
        <div class="message {{ category }}">{{ message }}</div>
    {% endfor %}
{% endwith %}
```

`flash()` stores a one-time message in the session. On the next request, `get_flashed_messages()` retrieves it. Jinja loops through the messages and safely escapes printed values by default.

## The hidden CSRF field

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

The user does not see this input, but the browser submits it. The server compares it with the token in the signed session.

## Login and logout forms

The login form posts to `/login`. The logout form posts to `/logout`. Using a link for logout would make logout a GET action, which is easier to trigger unintentionally or cross-site.

## CSS selectors

CSS follows this shape:

```css
selector {
    property: value;
}
```

Examples:

- `body` selects every body element.
- `.login-card` selects elements whose class includes `login-card`.
- `button:hover` selects a button while the pointer is over it.
- `.operations-page::before` creates the fixed grid background.
- `input:not([type="hidden"])` selects inputs except hidden inputs.

## The box model

Every element has content, padding, border, and margin. This rule simplifies width calculations:

```css
* {
    box-sizing: border-box;
}
```

With `border-box`, a declared width includes padding and border.

## Centering the form

```css
.login-page {
    display: grid;
    place-items: center;
    min-height: 100vh;
}
```

CSS Grid turns the body into a grid container. `place-items: center` centers the single card horizontally and vertically. `100vh` is 100 percent of the viewport height.

## Design tokens and themes

The stylesheet uses custom properties instead of duplicating every shared color:

```css
:root {
    --page: #111315;
    --surface: #191c1f;
    --text: #f1f2f3;
    --line: #30353a;
}

html[data-theme="light"] {
    --page: #f3f1ea;
    --surface: #fcfbf7;
    --text: #202422;
    --line: #d7d4ca;
}
```

`theme.js` chooses a saved preference or the operating-system preference, sets `data-theme`, and stores later changes in `localStorage`. Supported browsers reveal the new theme as a radial wave from the toggle. The fallback fades theme-sensitive properties, and `prefers-reduced-motion` disables decorative motion when requested by the user.

Theme-specific rules cover interaction states as well as page backgrounds. Event-row hover colors, warning and danger states, code panels, lab progress, and switches each receive a light-mode treatment so dark surfaces do not leak into the light interface.

## Responsive sizing functions

```css
width: min(100%, 380px);
font-size: clamp(72px, 14vw, 200px);
```

`min()` chooses the smaller value, so the card never exceeds 380 px but can shrink on small screens. `clamp(minimum, preferred, maximum)` keeps the welcome text between 72 px and 200 px while allowing viewport-based scaling.

## The signal field and analyst brief

The dashboard does not depend on a chart library. JavaScript converts the twelve hourly API buckets into a semantic grid. Each critical, warning, or informational cell receives an intensity value through the `--level` CSS property. The current hour receives a separate marker.

The analyst brief derives a posture from the same response. It updates the posture label, pressure dial, explanation, and suggested next action. These are presentation aids rather than a replacement for the underlying event evidence.

## Event-stream layout

The event table uses `table-layout: fixed` with explicit proportional columns. Cells use `overflow-wrap: anywhere` and normal whitespace, allowing long sources and messages to wrap instead of widening the entire page. On narrower screens, padding and label sizes shrink while the data remains visible.

Pagination always includes the first and last page. When more than seven pages exist, JavaScript adds the current page and its neighbors with ellipses between separated ranges.

## Media queries

```css
@media (max-width: 700px) {
    .signal-labels { display: none; }
    .theme-toggle em { display: none; }
}
```

This rule applies only on narrow screens, removing labels whose meaning is already communicated by color and accessible text while keeping the controls usable.
