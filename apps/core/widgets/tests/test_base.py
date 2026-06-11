"""Tests for shared widget infrastructure (sizes + validation states)."""
from django import forms

from apps.core.widgets._base import (
    SIZE_CLASSES,
    STATE_CLASSES,
    field_state,
    field_state_classes,
)

# ── Sizing ─────────────────────────────────────────────────────────────


def test_size_classes_has_three_keys():
    assert set(SIZE_CLASSES.keys()) == {"sm", "md", "lg"}


def test_each_size_has_input_and_label_keys():
    for spec in SIZE_CLASSES.values():
        assert "input" in spec
        assert "label" in spec


def test_md_is_the_default_height():
    """h-10 + text-sm match the inputs already used across the project."""
    assert SIZE_CLASSES["md"]["input"] == "h-10 text-sm"


# ── State classes ──────────────────────────────────────────────────────


def test_state_classes_cover_all_four_states():
    assert set(STATE_CLASSES.keys()) == {"default", "success", "warning", "error"}


def test_field_state_classes_known_state():
    assert "border-success" in field_state_classes("success")
    assert "border-destructive" in field_state_classes("error")


def test_field_state_classes_unknown_falls_back_to_default():
    assert field_state_classes("nonsense") == STATE_CLASSES["default"]  # type: ignore[arg-type]


# ── field_state() resolution ───────────────────────────────────────────


class _ProbeForm(forms.Form):
    name = forms.CharField(required=True, max_length=10)


def test_field_state_default_for_unbound_field():
    form = _ProbeForm()
    assert field_state(form["name"]) == "default"


def test_field_state_error_when_form_has_validation_errors():
    """A bound form whose field failed validation auto-renders 'error'."""
    form = _ProbeForm(data={"name": "way too long for the limit"})
    assert form.is_valid() is False
    assert field_state(form["name"]) == "error"


def test_field_state_explicit_data_state_overrides_default():
    form = _ProbeForm()
    form.fields["name"].widget.attrs["data-state"] = "success"
    assert field_state(form["name"]) == "success"


def test_field_state_explicit_data_state_takes_precedence_over_errors():
    """Explicit success state wins even if the form has errors — useful
    for async-validated fields where the server has already cleared the value."""
    form = _ProbeForm(data={"name": "too long for the limit"})
    form.is_valid()
    form.fields["name"].widget.attrs["data-state"] = "success"
    assert field_state(form["name"]) == "success"


def test_field_state_handles_none_input():
    """field_state(None) doesn't blow up."""
    assert field_state(None) == "default"


def test_field_state_ignores_unknown_data_state():
    form = _ProbeForm()
    form.fields["name"].widget.attrs["data-state"] = "zorblax"
    assert field_state(form["name"]) == "default"
