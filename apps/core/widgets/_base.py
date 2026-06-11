"""Shared widget infrastructure.

Two pieces of plumbing every Phase 12 widget needs:

1. **Sizing**: every widget supports sm / md / lg via Tailwind class lookup.
   Widgets pass `size=` to their constructor; templates read it from
   `widget.size` and apply the matching class.

2. **Validation state**: widgets need to render in one of four visual
   states (default / success / warning / error). State comes from:
     - explicit `data-state` on the widget root (set by the view)
     - the bound form's `BoundField.errors` (auto-mapped to "error")

   The `_field_wrapper.html` template uses `field_state(bound_field)` to
   compute the state at render time.

Widgets themselves live in dedicated modules (inputs.py, choice.py, etc.)
that land in commits 3–6.
"""
from __future__ import annotations

from typing import Literal

WidgetSize = Literal["sm", "md", "lg"]
WidgetState = Literal["default", "success", "warning", "error"]

# Tailwind class lookups. The "input" key is the inner control (height +
# text size); the "label" key is the floating-label text size.
SIZE_CLASSES: dict[WidgetSize, dict[str, str]] = {
    "sm": {"input": "h-8 text-sm", "label": "text-xs"},
    "md": {"input": "h-10 text-sm", "label": "text-sm"},
    "lg": {"input": "h-12 text-base", "label": "text-base"},
}

STATE_CLASSES: dict[WidgetState, str] = {
    "default": "border-input focus:ring-ring/50 focus:border-ring",
    "success": "border-success/60 focus:ring-success/30 focus:border-success",
    "warning": "border-amber-500/60 focus:ring-amber-500/30 focus:border-amber-500",
    "error":   "border-destructive/60 focus:ring-destructive/30 focus:border-destructive",
}


def field_state(bound_field) -> WidgetState:
    """Resolve the state for a bound form field.

    Precedence:
      1. Explicit `data-state` on the widget's `attrs` (view override).
      2. "error" if the BoundField has any errors.
      3. "default" otherwise.

    Pass a Django BoundField (i.e. `form["name"]`); falls through safely
    on None.
    """
    if bound_field is None:
        return "default"
    explicit = bound_field.field.widget.attrs.get("data-state")
    if explicit in {"success", "warning", "error"}:
        return explicit  # type: ignore[return-value]
    if getattr(bound_field, "errors", None):
        return "error"
    return "default"


def field_state_classes(state: WidgetState) -> str:
    """Tailwind classes for the given state."""
    return STATE_CLASSES.get(state, STATE_CLASSES["default"])


class WrappableWidget:
    """Mixin for widgets that render inside the shared `_field_wrapper.html`.

    Sets up a uniform constructor signature so views can pass
    `size`, `icon`, `helper`, `state` consistently across widget types.
    Concrete widgets define `template_name` and `Media` themselves.

    Phase 12 commit 2: this mixin only stores the kwargs and exposes
    them via `get_context()`. Concrete widget classes (FloatingLabelInput
    etc.) land in commits 3–6 and inherit from both this mixin and a
    Django widget class.
    """

    def __init__(self, *,
                 size: WidgetSize = "md",
                 helper: str | None = None,
                 state: WidgetState | None = None,
                 attrs=None,
                 **kwargs):
        # Forward to whichever Django widget is in our MRO. Concrete
        # subclasses pass through to TextInput / Textarea / Select / etc.
        super().__init__(attrs=attrs, **kwargs)
        self.size: WidgetSize = size if size in SIZE_CLASSES else "md"
        self.helper = helper
        # Surface explicit state via attrs so field_state() can pick it up.
        if state in {"success", "warning", "error"}:
            self.attrs["data-state"] = state

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        size_cls = SIZE_CLASSES[self.size]
        ctx["widget"].update({
            "size": self.size,
            "size_input_classes": size_cls["input"],
            "size_label_classes": size_cls["label"],
            "helper": self.helper,
            "state_classes": STATE_CLASSES["default"],  # field_state() may override
        })
        return ctx
