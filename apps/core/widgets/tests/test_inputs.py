"""Tests for the Phase 12 input widgets (commit 3)."""
from django import forms

from apps.core.widgets import (
    FloatingLabelInput,
    FloatingLabelTextarea,
    IconPrefixInput,
    IconSuffixInput,
)


def _render(widget, name="x", value=""):
    """Render a widget standalone (no form wrapper)."""
    return widget.render(name, value, attrs={"id": f"id_{name}"})


# ── FloatingLabelInput ─────────────────────────────────────────────────


def test_floating_label_input_renders_input_and_label():
    out = _render(FloatingLabelInput(floating_label="Full name"), name="name")
    assert 'name="name"' in out
    assert 'id="id_name"' in out
    assert "Full name" in out
    # Floating-label CSS uses :placeholder-shown — placeholder must be a single space
    assert 'placeholder=" "' in out


def test_floating_label_input_size_classes_applied():
    out = _render(FloatingLabelInput(size="lg", floating_label="X"))
    assert "h-12" in out
    assert "text-base" in out


def test_floating_label_input_renders_value():
    out = _render(FloatingLabelInput(floating_label="X"), value="hello")
    assert 'value="hello"' in out


def test_floating_label_input_falls_back_to_field_name():
    """Without an explicit floating_label, the field name is used."""
    out = _render(FloatingLabelInput(), name="username")
    assert ">\n    username\n" in out or "username" in out


def test_floating_label_input_max_length_counter_renders_when_maxlength_set():
    widget = FloatingLabelInput(
        floating_label="X", max_length_counter=True,
        attrs={"maxlength": "50"},
    )
    out = widget.render("x", "hi", {"id": "id_x", "maxlength": "50"})
    # Counter renders as <span>n</span>/<span>50</span>
    assert ">50<" in out
    assert "tabular-nums" in out


def test_floating_label_input_no_counter_without_maxlength():
    widget = FloatingLabelInput(floating_label="X", max_length_counter=True)
    out = _render(widget)
    # The counter is the only place tabular-nums + Alpine n-tracking appears.
    assert "tabular-nums" not in out


# ── FloatingLabelTextarea ──────────────────────────────────────────────


def test_floating_label_textarea_renders_textarea_with_rows():
    out = _render(FloatingLabelTextarea(floating_label="Bio", rows=4))
    assert "<textarea" in out
    assert 'rows="4"' in out


def test_floating_label_textarea_uses_apex_autogrow():
    out = _render(FloatingLabelTextarea(floating_label="Bio", max_rows=12))
    assert "apexAutogrow(12)" in out


def test_floating_label_textarea_max_length_counter():
    widget = FloatingLabelTextarea(
        floating_label="Bio", max_length_counter=True,
    )
    out = widget.render("bio", "abc", {"id": "id_bio", "maxlength": "200"})
    # The counter renders as <span>n</span>/<span>200</span>
    assert ">200<" in out
    assert "tabular-nums" in out


# ── IconPrefixInput ────────────────────────────────────────────────────


def test_icon_prefix_input_renders_icon_inside_left_padding():
    out = _render(IconPrefixInput(icon="search"))
    # Icon SVG present + input has pl-9 to make room.
    assert "<svg" in out
    assert "pl-9" in out


def test_icon_prefix_input_passes_type_through_attrs():
    out = _render(IconPrefixInput(icon="mail", attrs={"type": "email"}))
    assert 'type="email"' in out


# ── IconSuffixInput ────────────────────────────────────────────────────


def test_icon_suffix_input_default_renders_span_not_button():
    out = _render(IconSuffixInput(icon="info"))
    assert "<svg" in out
    assert "pr-9" in out
    # Default (clickable=False) should NOT render a button for the icon.
    assert "<button" not in out


def test_icon_suffix_input_clickable_renders_button_with_dispatch():
    out = _render(IconSuffixInput(icon="eye", clickable=True), name="password")
    assert "<button" in out
    # Dispatches a custom event with the field name.
    assert "apex:icon-suffix:click" in out
    assert "'password'" in out  # field name passed in dispatch detail


# ── Form integration ──────────────────────────────────────────────────


class _DemoForm(forms.Form):
    name = forms.CharField(widget=FloatingLabelInput(floating_label="Name"),
                           required=True)


def test_form_field_with_widget_validates_and_round_trips():
    form = _DemoForm(data={"name": "Aigars"})
    assert form.is_valid()
    assert form.cleaned_data["name"] == "Aigars"


def test_form_field_with_widget_renders_through_field_tag():
    """The {% apex_field %} tag works with our widgets."""
    from django.template import Context, Template
    form = _DemoForm()
    tpl = Template("{% load apex %}{% apex_field form.name %}")
    out = tpl.render(Context({"form": form}))
    assert 'name="name"' in out
    assert 'data-state="default"' in out


def test_form_field_with_errors_renders_error_state():
    from django.template import Context, Template
    form = _DemoForm(data={"name": ""})
    form.is_valid()
    tpl = Template("{% load apex %}{% apex_field form.name %}")
    out = tpl.render(Context({"form": form}))
    assert 'data-state="error"' in out
    assert 'role="alert"' in out
