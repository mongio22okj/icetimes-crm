"""Tests for the {% apex_field %} inclusion tag wrapping a BoundField."""
from django import forms
from django.template import Context, Template


class _Form(forms.Form):
    title = forms.CharField(required=True, max_length=80, label="Title",
                            help_text="Short, descriptive.")
    notes = forms.CharField(required=False, widget=forms.Textarea(), label="Notes")


def _render(form):
    """Render an apex_field tag against the given form's `title` field."""
    tpl = Template(
        "{% load apex %}{% apex_field form.title %}"
    )
    return tpl.render(Context({"form": form}))


def test_renders_label_and_widget():
    out = _render(_Form())
    assert "Title" in out
    assert 'name="title"' in out
    assert "<label" in out


def test_required_field_renders_asterisk():
    out = _render(_Form())
    assert "*" in out


def test_helper_text_rendered_in_default_state():
    out = _render(_Form())
    assert "Short, descriptive." in out


def test_helper_text_replaced_by_error_when_invalid():
    form = _Form(data={"title": "x" * 100})  # exceeds max_length=80
    form.is_valid()
    out = _render(form)
    assert 'role="alert"' in out
    # Helper text is suppressed when an error is shown
    assert "Short, descriptive." not in out


def test_state_attribute_on_wrapper_div_reflects_validation():
    form = _Form(data={"title": ""})
    form.is_valid()
    out = _render(form)
    assert 'data-state="error"' in out


def test_default_state_when_unbound():
    out = _render(_Form())
    assert 'data-state="default"' in out


def test_label_for_matches_widget_id():
    """The wrapper's <label for=...> must match Django's auto-generated
    widget id so screen readers associate them correctly.
    """
    out = _render(_Form())
    assert 'for="id_title"' in out
    assert 'id="id_title"' in out


def test_optional_field_no_asterisk():
    tpl = Template("{% load apex %}{% apex_field form.notes %}")
    out = tpl.render(Context({"form": _Form()}))
    # The label still renders; just no required asterisk.
    assert "Notes" in out
    # No required asterisk in the label area (look for the destructive span).
    assert 'text-destructive ml-0.5' not in out


def test_label_can_be_overridden():
    tpl = Template('{% load apex %}{% apex_field form.title label="Custom Heading" %}')
    out = tpl.render(Context({"form": _Form()}))
    assert "Custom Heading" in out
    # Original label "Title" no longer appears as a label
    assert "Title" not in out.split("Custom Heading")[1]


def test_label_above_false_suppresses_label():
    tpl = Template('{% load apex %}{% apex_field form.title label_above=False %}')
    out = tpl.render(Context({"form": _Form()}))
    # Widget still renders, label tag does not
    assert 'name="title"' in out
    assert "<label" not in out
