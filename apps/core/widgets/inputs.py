"""Single-line and multi-line text inputs.

All inputs in this module subclass `WrappableWidget` for the shared
size + state plumbing. Each widget defines its own `template_name`
under `templates/widgets/` and reads its specific options out of
`get_context()`.

For label rendering, callers use the `{% apex_field %}` template tag
which wraps the widget in `_field_wrapper.html`. The widget itself
just renders the input control.
"""
from django import forms

from apps.core.widgets._base import WrappableWidget


class FloatingLabelInput(WrappableWidget, forms.TextInput):
    """Single-line input with a label that floats inside the field.

    The label is rendered inside the input's relative container at
    render time. When the input is empty + unfocused, the label sits
    centered (placeholder-like). On focus or when the field has a
    value, it floats up to a small size in the top-left corner.

    Args:
        size: sm | md | lg (default md)
        helper: text shown below in default/success/warning states
        floating_label: text shown inside; defaults to bound field's label
        max_length_counter: when True, render `n / max` below the input
        attrs: passed through to the underlying <input>
    """
    template_name = "widgets/floating_label_input.html"

    def __init__(self, *, floating_label: str | None = None,
                 max_length_counter: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.floating_label = floating_label
        self.max_length_counter = max_length_counter

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["floating_label"] = self.floating_label
        ctx["widget"]["max_length_counter"] = self.max_length_counter
        return ctx


class FloatingLabelTextarea(WrappableWidget, forms.Textarea):
    """Multi-line variant. Auto-grows up to `max_rows` via Alpine.

    Args:
        size: sm | md | lg (default md)
        helper: text shown below
        floating_label: text shown inside
        rows: initial visible rows (default 3)
        max_rows: cap for auto-grow (default 10)
        max_length_counter: when True, render `n / max` below
    """
    template_name = "widgets/floating_label_textarea.html"

    def __init__(self, *, floating_label: str | None = None,
                 rows: int = 3, max_rows: int = 10,
                 max_length_counter: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.floating_label = floating_label
        self.rows = rows
        self.max_rows = max_rows
        self.max_length_counter = max_length_counter

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["floating_label"] = self.floating_label
        ctx["widget"]["rows"] = self.rows
        ctx["widget"]["max_rows"] = self.max_rows
        ctx["widget"]["max_length_counter"] = self.max_length_counter
        # Suppress Django's default rows attribute; we set it ourselves
        # so the textarea matches our height calc.
        ctx["widget"]["attrs"]["rows"] = self.rows
        return ctx


class IconPrefixInput(WrappableWidget, forms.TextInput):
    """Input with a Lucide icon inside the left edge.

    Args:
        size: sm | md | lg (default md)
        icon: lucide icon name (e.g. "search", "mail")
        helper: text below
    """
    template_name = "widgets/icon_prefix_input.html"

    def __init__(self, *, icon: str = "search", **kwargs):
        super().__init__(**kwargs)
        self.icon = icon

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["icon"] = self.icon
        return ctx


class IconSuffixInput(WrappableWidget, forms.TextInput):
    """Input with a Lucide icon inside the right edge.

    `clickable=True` renders the icon as a <button> instead of a span,
    typically used for password show/hide or copy-to-clipboard. The
    button dispatches `apex:icon-suffix:click` so callers can hook in
    an Alpine handler without a custom widget.

    Args:
        size: sm | md | lg (default md)
        icon: lucide icon name
        clickable: when True, the icon becomes a real button
        helper: text below
    """
    template_name = "widgets/icon_suffix_input.html"

    def __init__(self, *, icon: str = "x", clickable: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.icon = icon
        self.clickable = clickable

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["icon"] = self.icon
        ctx["widget"]["clickable"] = self.clickable
        return ctx
