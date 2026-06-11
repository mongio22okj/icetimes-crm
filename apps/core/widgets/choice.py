"""Choice widgets — multi-select, tag input, combobox.

All three reuse the apex* Alpine factories already shipped in
static/js/shell.js (apexMultiSelect, apexTagInput, apexCombobox).
The widget classes are thin Django adapters that:

  - render the right hidden inputs so form submission carries values
  - serialize their initial state into Alpine
  - integrate with Django form validation via the standard Widget API
"""
from __future__ import annotations

import json

from django import forms

from apps.core.widgets._base import WrappableWidget


class MultiSelect(WrappableWidget, forms.SelectMultiple):
    """Tag-chip multi-select. Backs `forms.MultipleChoiceField` (or
    `forms.ModelMultipleChoiceField`).

    Args:
        choices: iterable of (value, label) — passed via the field, not the widget
        size: sm | md | lg (default md)
        helper: text below
        placeholder: shown when no chips selected
    """
    template_name = "widgets/multi_select.html"

    def __init__(self, *, placeholder: str = "Select…", **kwargs):
        super().__init__(**kwargs)
        self.placeholder = placeholder

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        # Resolve choices to a JSON-serializable list of {value, label}.
        # `widget.choices` is set by the field's __init__ (Django copies it
        # to the widget when the field is created).
        choices = list(self.choices) if hasattr(self, "choices") else []
        opts = [{"value": str(v), "label": str(label)} for v, label in choices]
        # Selected values: Django passes a list (or stringified single).
        if value is None:
            selected = []
        elif isinstance(value, list | tuple):
            selected = [str(v) for v in value]
        else:
            selected = [str(value)]
        ctx["widget"].update({
            "options_json": json.dumps(opts),
            "selected_json": json.dumps(selected),
            "placeholder": self.placeholder,
        })
        return ctx


class TagInput(WrappableWidget, forms.Widget):
    """Free-form tag entry. Stores a list of strings.

    Backs a `forms.CharField` whose value is a comma-separated string,
    or a custom field that does its own coercion. Use
    `value_from_datadict` to get back a list:

        from apps.core.widgets import TagInput
        class MyForm(forms.Form):
            tags = forms.CharField(widget=TagInput())

            def clean_tags(self):
                # `cleaned_data["tags"]` is already the joined string from
                # the form; split it back out as a list if needed.
                return [t.strip() for t in self.cleaned_data["tags"].split(",")
                        if t.strip()]

    Args:
        suggestions: optional list of strings shown as quick-add chips
    """
    template_name = "widgets/tag_input.html"

    def __init__(self, *, suggestions: list[str] | None = None,
                 placeholder: str = "Add a tag…", **kwargs):
        super().__init__(**kwargs)
        self.suggestions = list(suggestions or [])
        self.placeholder = placeholder

    def value_from_datadict(self, data, files, name):
        # Form posts the value as a comma-separated string under `name`.
        raw = data.get(name, "")
        return raw

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        # Value can be a list (initial=[…]) or a comma-separated string
        # (re-render after form invalid).
        if value is None or value == "":
            initial = []
        elif isinstance(value, list | tuple):
            initial = [str(v) for v in value]
        else:
            initial = [t.strip() for t in str(value).split(",") if t.strip()]
        ctx["widget"].update({
            "initial_json": json.dumps(initial),
            "suggestions_json": json.dumps(self.suggestions),
            "placeholder": self.placeholder,
        })
        return ctx


class Combobox(WrappableWidget, forms.Select):
    """Single-select typeahead. Backs `forms.ChoiceField` /
    `forms.ModelChoiceField`.

    `async_url` (when set) makes the widget fetch options from a URL
    via HTMX/Alpine. The URL should accept `?_typeahead=1&q=…` and
    return JSON: `[{"value": "1", "label": "Acme"}, …]`. Pair with
    `TypeaheadMixin` on the source view.

    `choices` (the static fallback) comes from the field automatically.

    Args:
        async_url: URL name for typeahead (resolved via Django reverse)
        placeholder: shown when no value selected
    """
    template_name = "widgets/combobox.html"

    def __init__(self, *, async_url: str | None = None,
                 placeholder: str = "Select…", **kwargs):
        super().__init__(**kwargs)
        self.async_url = async_url
        self.placeholder = placeholder

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        choices = list(self.choices) if hasattr(self, "choices") else []
        opts = [{"value": str(v), "label": str(label)} for v, label in choices if v]
        ctx["widget"].update({
            "options_json": json.dumps(opts),
            "selected_value": str(value) if value not in (None, "") else "",
            "selected_label": next(
                (o["label"] for o in opts if o["value"] == str(value)),
                "",
            ),
            "placeholder": self.placeholder,
            "async_url": self.async_url or "",
        })
        return ctx


class TypeaheadMixin:
    """Mixin for views that back a Combobox's `async_url`.

    Usage:

        class CustomerListView(TypeaheadMixin, ListView):
            model = Customer
            typeahead_fields = ("name", "email", "company")  # icontains-OR'd
            typeahead_limit = 20

    Adds an `_typeahead=1&q=…` mode that returns JSON option list. Falls
    through to the normal view rendering for non-typeahead requests.
    """
    typeahead_fields: tuple[str, ...] = ()
    typeahead_limit: int = 20

    def filter_typeahead(self, qs, q: str):
        """Default OR-icontains filter across `typeahead_fields`."""
        from django.db.models import Q
        q = (q or "").strip()
        if not q or not self.typeahead_fields:
            return qs
        cond = Q()
        for f in self.typeahead_fields:
            cond |= Q(**{f"{f}__icontains": q})
        return qs.filter(cond)

    def typeahead_label(self, obj) -> str:
        """Default label = str(obj). Override for richer labels."""
        return str(obj)

    def typeahead_value(self, obj) -> str:
        return str(obj.pk)

    def get(self, request, *args, **kwargs):
        if request.GET.get("_typeahead") == "1":
            from django.http import JsonResponse
            qs = self.filter_typeahead(self.get_queryset(),
                                       request.GET.get("q", ""))[:self.typeahead_limit]
            data = [{"value": self.typeahead_value(o),
                     "label": self.typeahead_label(o)} for o in qs]
            return JsonResponse(data, safe=False)
        return super().get(request, *args, **kwargs)
