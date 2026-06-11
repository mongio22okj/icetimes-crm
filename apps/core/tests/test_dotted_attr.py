"""Tests for the {{ obj|dotted_attr:'a.b.c' }} template filter."""
from types import SimpleNamespace

from apps.core.templatetags.apex import dotted_attr


def test_simple_attr():
    obj = SimpleNamespace(name="Aigars")
    assert dotted_attr(obj, "name") == "Aigars"


def test_nested_attr():
    inner = SimpleNamespace(email="x@y")
    obj = SimpleNamespace(owner=inner)
    assert dotted_attr(obj, "owner.email") == "x@y"


def test_missing_attr_returns_empty_string():
    obj = SimpleNamespace(name="x")
    assert dotted_attr(obj, "owner.email") == ""


def test_none_at_any_level_returns_empty_string():
    obj = SimpleNamespace(owner=None)
    assert dotted_attr(obj, "owner.email") == ""


def test_dict_lookup_falls_back_to_subscript():
    obj = SimpleNamespace(meta={"role": "admin"})
    assert dotted_attr(obj, "meta.role") == "admin"


def test_callable_leaf_is_invoked():
    obj = SimpleNamespace(get_name=lambda: "computed")
    assert dotted_attr(obj, "get_name") == "computed"


def test_callable_with_required_args_is_returned_as_is():
    obj = SimpleNamespace(formatter=lambda x, y: x + y)
    # Cannot be called without args — filter falls through to returning the callable.
    out = dotted_attr(obj, "formatter")
    assert callable(out)


def test_none_input_returns_empty_string():
    assert dotted_attr(None, "anything") == ""
