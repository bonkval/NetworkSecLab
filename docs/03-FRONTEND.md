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
- `.dashboard-page::before` creates a pseudo-element.
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

## Background shorthand

```css
background: #030407 url("../images/background.jpg") center / cover no-repeat fixed;
```

This combines:

- A fallback color
- An image URL relative to the CSS file
- Centered positioning
- `cover` sizing so the image fills the viewport
- No tiling
- A fixed background during scrolling

From `app/static/css/style.css`, `../images/` means go up from `css` to `static`, then into `images`.

## The glass card

`rgba(5, 7, 11, 0.78)` is nearly black with 78% opacity. `backdrop-filter: blur(12px)` blurs what appears behind the card. `box-shadow` creates depth. These properties affect appearance only; the form remains normal HTML.

## Responsive sizing functions

```css
width: min(100%, 380px);
font-size: clamp(72px, 14vw, 200px);
```

`min()` chooses the smaller value, so the card never exceeds 380 px but can shrink on small screens. `clamp(minimum, preferred, maximum)` keeps the welcome text between 72 px and 200 px while allowing viewport-based scaling.

## Creating the white wave page

The dashboard reuses the same image in a pseudo-element:

```css
.dashboard-page::before {
    filter: invert(1) grayscale(1);
    opacity: 0.23;
}
```

`invert(1)` reverses colors; `grayscale(1)` removes color; low opacity blends it into the white background. This avoids storing a duplicate image.

## Layering

The pseudo-element is fixed behind normal positioned content. `.welcome` uses `position: relative`, while the logout form uses `position: fixed` and `z-index: 1` so it remains visible above the decorative layer.

## Media queries

```css
@media (max-width: 480px) {
    .login-card { padding: 28px 22px; }
}
```

This rule applies only on narrow screens, reducing card padding so the form fits comfortably.
