from django.template.loader import render_to_string
from django.test import RequestFactory


def test_header_renders_theme_toggle():
    html = render_to_string("partials/header.html", {"request": RequestFactory().get("/")})
    assert 'aria-label="Toggle theme"' in html
    assert 'toggleTheme()' in html  # delegates to apexShell.toggleTheme()


def test_theme_toggle_delegates_to_shell():
    html = render_to_string("partials/header.html", {"request": RequestFactory().get("/")})
    # Inline localStorage write has moved into apexShell.toggleTheme() in static/js/shell.js.
    assert 'toggleTheme()' in html
    assert "localStorage.setItem('theme'" not in html


def test_header_includes_palette_trigger():
    html = render_to_string("partials/header.html", {"request": RequestFactory().get("/")})
    # Search input became a palette-trigger button with ⌘K hint.
    assert 'openPalette()' in html
    assert 'Search...' in html
    assert '⌘' in html


def test_header_includes_hamburger():
    html = render_to_string("partials/header.html", {"request": RequestFactory().get("/")})
    assert 'aria-label="Open menu"' in html
    assert 'drawer.open = true' in html


def test_dashboard_layout_renders_sidebar_and_header():
    html = render_to_string("layouts/dashboard.html", {}, request=RequestFactory().get("/"))
    # Sidebar markers
    assert 'Main navigation' in html  # aria-label from Task 2 fix
    # Header markers
    assert 'Toggle theme' in html
    assert 'openPalette()' in html
