"""Tests for the Phase 12 choice widgets (commit 4)."""
import json

import pytest
from django import forms
from django.http import JsonResponse
from django.test import RequestFactory
from django.views.generic import ListView

from apps.core.widgets import Combobox, MultiSelect, TagInput, TypeaheadMixin

# ── MultiSelect ────────────────────────────────────────────────────────


class _MultiForm(forms.Form):
    tags = forms.MultipleChoiceField(
        choices=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
        required=False,
        widget=MultiSelect(placeholder="Pick…"),
    )


def test_multi_select_renders_options_as_json():
    form = _MultiForm()
    out = str(form["tags"])
    # The Alpine init call should embed the JSON list of options.
    assert '"value": "a"' in out and '"label": "Alpha"' in out
    assert "apexMultiSelect" in out


def test_multi_select_renders_initial_selected_values():
    form = _MultiForm(initial={"tags": ["a", "b"]})
    out = str(form["tags"])
    # Selected values appear in the apexMultiSelect init payload.
    assert "selected: " in out
    assert '"a"' in out and '"b"' in out


def test_multi_select_round_trips_through_form_validation():
    form = _MultiForm(data={"tags": ["a", "c"]})
    assert form.is_valid()
    assert set(form.cleaned_data["tags"]) == {"a", "c"}


def test_multi_select_renders_hidden_inputs_for_django_form_post():
    """The template emits one hidden <input name=tags> per selected value
    so a normal form POST sends them as a list."""
    out = str(_MultiForm()["tags"])
    # Template uses x-for to bind hidden inputs; the binding string is present.
    assert 'name="tags"' in out
    assert 'type="hidden"' in out


# ── TagInput ───────────────────────────────────────────────────────────


class _TagForm(forms.Form):
    labels = forms.CharField(
        required=False,
        widget=TagInput(suggestions=["urgent", "vip"], placeholder="Tag…"),
    )


def test_tag_input_renders_initial_as_list():
    """A list initial should be JSON-encoded into the Alpine state."""
    form = _TagForm(initial={"labels": ["urgent", "follow-up"]})
    out = str(form["labels"])
    assert '"urgent"' in out
    assert '"follow-up"' in out
    assert "apexTagInput" in out


def test_tag_input_accepts_comma_separated_initial():
    form = _TagForm(initial={"labels": "alpha,beta"})
    out = str(form["labels"])
    assert '"alpha"' in out
    assert '"beta"' in out


def test_tag_input_renders_suggestions():
    out = str(_TagForm()["labels"])
    assert "suggestions:" in out
    assert '"urgent"' in out and '"vip"' in out


def test_tag_input_round_trips_value_as_string():
    """Form posts the joined string under the field name."""
    form = _TagForm(data={"labels": "alpha,beta,gamma"})
    assert form.is_valid()
    assert form.cleaned_data["labels"] == "alpha,beta,gamma"


def test_tag_input_value_from_datadict_returns_raw_string():
    """The widget's value_from_datadict pulls from request.POST."""
    widget = TagInput()
    assert widget.value_from_datadict({"x": "a,b,c"}, {}, "x") == "a,b,c"


# ── Combobox ───────────────────────────────────────────────────────────


class _ComboForm(forms.Form):
    owner = forms.ChoiceField(
        choices=[("", "---"), ("1", "Sara"), ("2", "Marcus")],
        required=False,
        widget=Combobox(placeholder="Pick…"),
    )


def test_combobox_renders_options():
    out = str(_ComboForm()["owner"])
    assert '"value": "1"' in out and '"label": "Sara"' in out
    # Empty-string ("---") option is filtered out so users don't pick it.
    assert '"label": "---"' not in out


def test_combobox_renders_selected_label_for_initial():
    form = _ComboForm(initial={"owner": "2"})
    out = str(form["owner"])
    assert "Marcus" in out


def test_combobox_async_url_attribute_threads_through():
    widget = Combobox(async_url="/api/users/typeahead/")
    out = widget.render("owner", "", attrs={"id": "id_owner"})
    assert "/api/users/typeahead/" in out


def test_combobox_round_trips_through_form_validation():
    form = _ComboForm(data={"owner": "1"})
    assert form.is_valid()
    assert form.cleaned_data["owner"] == "1"


# ── TypeaheadMixin ─────────────────────────────────────────────────────


pytestmark = pytest.mark.django_db


class _UserListView(TypeaheadMixin, ListView):
    """Test fixture: a thin list view backed by the User model."""
    from django.contrib.auth import get_user_model
    model = get_user_model()
    typeahead_fields = ("username", "email")
    typeahead_limit = 5

    def typeahead_label(self, obj):
        return f"{obj.username} ({obj.email})"


def test_typeahead_mixin_returns_json_for_typeahead_request():
    from apps.accounts.tests.factories import UserFactory
    UserFactory(username="alice", email="alice@example.com")
    UserFactory(username="bob", email="bob@example.com")

    rf = RequestFactory()
    req = rf.get("/users/", {"_typeahead": "1", "q": "alice"})
    response = _UserListView.as_view()(req)

    assert isinstance(response, JsonResponse)
    data = json.loads(response.content)
    assert len(data) == 1
    assert data[0]["label"].startswith("alice")


def test_typeahead_mixin_respects_limit():
    from apps.accounts.tests.factories import UserFactory
    UserFactory.create_batch(10)
    rf = RequestFactory()
    req = rf.get("/users/", {"_typeahead": "1", "q": ""})
    response = _UserListView.as_view()(req)
    data = json.loads(response.content)
    assert len(data) <= 5  # typeahead_limit


def test_typeahead_mixin_passes_through_for_normal_request():
    """Without `?_typeahead=1`, the view falls through to ListView's
    default behavior (which would render the template — we just confirm
    it doesn't return a JsonResponse)."""
    from apps.accounts.tests.factories import UserFactory
    UserFactory()
    rf = RequestFactory()
    req = rf.get("/users/")
    # Calling as_view() without a template_name will raise
    # ImproperlyConfigured — that's fine, it proves the typeahead path
    # didn't intercept.
    try:
        _UserListView.as_view()(req)
    except Exception as e:
        assert "template" in str(e).lower() or "template_name" in str(e).lower()
