"""Toast bridge tests for apps.core.messages."""
from django.contrib.messages import get_messages
from django.contrib.messages.storage import default_storage
from django.test import RequestFactory

from apps.core.messages import (
    LEVEL_ERROR,
    LEVEL_INFO,
    LEVEL_SUCCESS,
    parse_extra_tags,
    toast,
)


def _request_with_messages():
    rf = RequestFactory()
    req = rf.get("/")
    # Attach a session + messages storage so add_message works.
    req.session = {}
    req._messages = default_storage(req)
    return req


def test_toast_pushes_simple_message():
    req = _request_with_messages()
    toast(req, LEVEL_SUCCESS, "Saved.")
    msgs = list(get_messages(req))
    assert len(msgs) == 1
    assert str(msgs[0]) == "Saved."
    assert msgs[0].level_tag == "success"
    # No extras
    assert msgs[0].extra_tags == ""


def test_toast_persistent_flag_round_trips():
    req = _request_with_messages()
    toast(req, LEVEL_INFO, "Heads up.", persistent=True)
    msgs = list(get_messages(req))
    meta = parse_extra_tags(msgs[0].extra_tags)
    assert meta["persistent"] is True
    assert meta["action"] is None


def test_toast_action_flag_round_trips():
    req = _request_with_messages()
    toast(req, LEVEL_SUCCESS, "Invoice sent.",
          action={"label": "View", "url": "/invoices/1/"})
    msgs = list(get_messages(req))
    meta = parse_extra_tags(msgs[0].extra_tags)
    assert meta["action"] == {"label": "View", "url": "/invoices/1/"}
    assert meta["persistent"] is False


def test_toast_action_and_persistent_combine():
    req = _request_with_messages()
    toast(req, LEVEL_ERROR, "Something failed.",
          action={"label": "Retry", "url": "/retry/"},
          persistent=True)
    msgs = list(get_messages(req))
    meta = parse_extra_tags(msgs[0].extra_tags)
    assert meta["persistent"] is True
    assert meta["action"]["label"] == "Retry"


def test_parse_extra_tags_empty_string():
    meta = parse_extra_tags("")
    assert meta == {"action": None, "persistent": False, "other_tags": []}


def test_parse_extra_tags_preserves_unknown_tags():
    meta = parse_extra_tags("custom-tag persistent")
    assert meta["persistent"] is True
    assert "custom-tag" in meta["other_tags"]


def test_parse_extra_tags_skips_malformed_action():
    # Missing url part — must not blow up
    meta = parse_extra_tags("action::OnlyLabel")
    assert meta["action"] is None
