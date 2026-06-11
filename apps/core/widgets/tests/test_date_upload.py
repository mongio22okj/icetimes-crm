"""Tests for the Phase 12 date + upload widgets (commit 5)."""
import io
import json
from datetime import date

import pytest
from django import forms
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.core.widgets import DateRangePicker, FileDropzone

# ── DateRangePicker ────────────────────────────────────────────────────


class _RangeForm(forms.Form):
    period = forms.CharField(required=False, widget=DateRangePicker())


def test_date_range_picker_parses_comma_joined_string():
    form = _RangeForm(initial={"period": "2026-04-01,2026-04-30"})
    out = str(form["period"])
    assert "2026-04-01" in out
    assert "2026-04-30" in out


def test_date_range_picker_parses_tuple_initial():
    form = _RangeForm(initial={"period": (date(2026, 1, 1), date(2026, 1, 31))})
    out = str(form["period"])
    assert "2026-01-01" in out
    assert "2026-01-31" in out


def test_date_range_picker_handles_empty_initial():
    out = str(_RangeForm()["period"])
    # Alpine factory invocation with empty from/to.
    assert 'apexDateRange({from: "", to: ""})' in out
    # Trigger button + popover render even with no value.
    assert 'data-widget="date-range-picker"' in out


def test_date_range_picker_round_trips_comma_joined_value():
    form = _RangeForm(data={"period": "2026-05-01,2026-05-15"})
    assert form.is_valid()
    assert form.cleaned_data["period"] == "2026-05-01,2026-05-15"


def test_date_range_picker_renders_alpine_factory():
    out = str(_RangeForm()["period"])
    assert "apexDateRange" in out


def test_date_range_picker_with_presets_default_true():
    """The preset shortcuts (Today, Last 7 days, etc.) render by default."""
    out = str(_RangeForm()["period"])
    assert "Today" in out
    assert "Last 7 days" in out


def test_date_range_picker_without_presets():
    class F(forms.Form):
        period = forms.CharField(
            required=False,
            widget=DateRangePicker(with_presets=False),
        )
    out = str(F()["period"])
    assert "Today" not in out
    assert "Last 7 days" not in out


# ── FileDropzone ───────────────────────────────────────────────────────


class _UploadForm(forms.Form):
    files = forms.CharField(
        required=False,
        widget=FileDropzone(
            upload_url="/upload/",
            accept="image/*,.pdf",
            max_files=3,
            max_size_mb=2,
        ),
    )


def test_file_dropzone_renders_with_upload_url():
    out = str(_UploadForm()["files"])
    assert "/upload/" in out
    assert "apexDropzone" in out


def test_file_dropzone_renders_accept_and_caps():
    out = str(_UploadForm()["files"])
    assert "image/*,.pdf" in out
    assert "max" in out  # the visible caption mentions caps
    # Caps thread through to the apexDropzone init.
    assert "maxFiles: 3" in out
    assert "maxSizeMB: 2" in out


def test_file_dropzone_url_name_is_resolved_via_reverse():
    """When upload_url is a URL name (not a path), it gets reversed."""
    class F(forms.Form):
        files = forms.CharField(
            required=False,
            widget=FileDropzone(upload_url="pages:forms_gallery_upload"),
        )
    out = str(F()["files"])
    # The resolved path appears in the rendered output.
    assert "/pages/forms/_upload/" in out


def test_file_dropzone_initial_ids_pre_populate():
    form = _UploadForm(initial={"files": "abc123,def456"})
    out = str(form["files"])
    # Initial IDs land in the apexDropzone init so they re-render after
    # form validation failures.
    assert "abc123" in out
    assert "def456" in out


def test_file_dropzone_round_trips_string_value():
    form = _UploadForm(data={"files": "id1,id2,id3"})
    assert form.is_valid()
    assert form.cleaned_data["files"] == "id1,id2,id3"


def test_file_dropzone_value_from_datadict_pulls_from_post():
    widget = FileDropzone()
    assert widget.value_from_datadict({"x": "a,b"}, {}, "x") == "a,b"


# ── Demo upload endpoint ───────────────────────────────────────────────


pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(db):
    return UserFactory(is_staff=True)


def test_forms_gallery_upload_endpoint_returns_json(client, staff):
    client.force_login(staff)
    fake_file = io.BytesIO(b"hello world")
    fake_file.name = "test.txt"
    r = client.post(reverse("pages:forms_gallery_upload"),
                    {"file": fake_file})
    assert r.status_code == 200
    assert r["Content-Type"] == "application/json"
    data = json.loads(r.content)
    assert data["name"] == "test.txt"
    assert data["size"] == 11
    assert "id" in data and len(data["id"]) > 0


def test_forms_gallery_upload_rejects_get(client, staff):
    client.force_login(staff)
    r = client.get(reverse("pages:forms_gallery_upload"))
    assert r.status_code == 400


def test_forms_gallery_upload_rejects_missing_file(client, staff):
    client.force_login(staff)
    r = client.post(reverse("pages:forms_gallery_upload"))
    assert r.status_code == 400


def test_forms_gallery_upload_requires_auth(client):
    fake_file = io.BytesIO(b"data")
    fake_file.name = "x.txt"
    r = client.post(reverse("pages:forms_gallery_upload"),
                    {"file": fake_file})
    # @login_required → redirect to login
    assert r.status_code in (301, 302)
