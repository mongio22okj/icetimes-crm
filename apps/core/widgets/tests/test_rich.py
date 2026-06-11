"""Tests for the Phase 12 RichText widget + helper integrations (commit 6)."""
from django import forms

from apps.core.widgets import RichText


class _RichForm(forms.Form):
    body = forms.CharField(required=False, widget=RichText())


def test_rich_text_renders_textarea():
    out = str(_RichForm()["body"])
    assert "<textarea" in out
    assert 'name="body"' in out


def test_rich_text_default_toolbar_is_basic():
    out = str(_RichForm()["body"])
    assert 'data-toolbar="basic"' in out


def test_rich_text_minimal_toolbar():
    class F(forms.Form):
        body = forms.CharField(required=False, widget=RichText(toolbar="minimal"))
    out = str(F()["body"])
    assert 'data-toolbar="minimal"' in out


def test_rich_text_full_toolbar():
    class F(forms.Form):
        body = forms.CharField(required=False, widget=RichText(toolbar="full"))
    out = str(F()["body"])
    assert 'data-toolbar="full"' in out


def test_rich_text_unknown_toolbar_falls_back_to_basic():
    class F(forms.Form):
        body = forms.CharField(required=False, widget=RichText(toolbar="zorp"))
    out = str(F()["body"])
    assert 'data-toolbar="basic"' in out


def test_rich_text_renders_initial_value_inside_textarea():
    form = _RichForm(initial={"body": "# Heading\n\nBody text."})
    out = str(form["body"])
    assert "# Heading" in out


def test_rich_text_round_trips_through_form_validation():
    form = _RichForm(data={"body": "## Hello"})
    assert form.is_valid()
    assert form.cleaned_data["body"] == "## Hello"


def test_rich_text_media_includes_easymde_assets():
    """The widget's Media class advertises its CSS + JS so callers can
    include them via {{ form.media }}."""
    out = str(_RichForm().media)
    assert "easymde.css" in out
    assert "easymde.js" in out


def test_rich_text_x_init_loads_easymde_when_available():
    """The template's x-init guards against EasyMDE being undefined."""
    out = str(_RichForm()["body"])
    assert "typeof EasyMDE" in out
    assert "new EasyMDE" in out


def test_rich_text_fallback_textarea_works_without_easymde():
    """Without EasyMDE loaded, the template still renders a usable textarea."""
    out = str(_RichForm()["body"])
    # Plain <textarea> is the foundation; EasyMDE just upgrades it.
    assert "<textarea" in out
    # The fallback textarea is sized + bordered.
    assert "min-h-32" in out
    assert "border-input" in out
