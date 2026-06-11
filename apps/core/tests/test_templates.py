from django.template.loader import render_to_string
from django.test import RequestFactory


def test_base_template_includes_apex_css():
    html = render_to_string("base.html", {"request": RequestFactory().get("/")})
    assert 'href="/static/css/app.css"' in html
    assert 'class="bg-background text-foreground' in html  # may have more classes


def test_base_template_has_theme_init_script():
    html = render_to_string("base.html", {"request": RequestFactory().get("/")})
    # Prevents dark-mode flash: must run before body
    assert 'localStorage.getItem("theme")' in html
    assert "document.documentElement.classList" in html
    theme_pos = html.index('localStorage.getItem("theme")')
    body_pos = html.index("<body")
    assert theme_pos < body_pos, "Theme init script must appear before <body> to prevent FOUC"
