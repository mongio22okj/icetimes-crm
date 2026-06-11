"""Rich text editor — Markdown via EasyMDE.

EasyMDE chosen over TipTap for: smaller bundle (~50KB vs ~200KB),
markdown-first matches the existing blog/help models, simpler keyboard
model, no headless complexity. Self-hosted under static/{js,css}/vendor/.

The widget loads its assets via head_extra in the gallery / form pages
where it's used — see templates/widgets/rich_text.html for the
include pattern. The vendor JS attaches to a single `<textarea>` and
takes over rendering.

Toolbar presets:
    minimal: bold, italic, link
    basic:   minimal + heading, list, quote, code
    full:    basic + table, image, preview, side-by-side
"""
from __future__ import annotations

from typing import Literal

from django import forms

from apps.core.widgets._base import WrappableWidget

ToolbarPreset = Literal["minimal", "basic", "full"]


class RichText(WrappableWidget, forms.Textarea):
    """Markdown editor backed by EasyMDE.

    Args:
        toolbar: minimal | basic | full (default basic)
        size: sm | md | lg (default md)
        helper: text below
        attrs: passed through to the underlying <textarea>
    """
    template_name = "widgets/rich_text.html"

    def __init__(self, *, toolbar: ToolbarPreset = "basic", **kwargs):
        super().__init__(**kwargs)
        self.toolbar = toolbar if toolbar in ("minimal", "basic", "full") else "basic"

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["toolbar"] = self.toolbar
        return ctx

    class Media:
        css = {"all": ("css/vendor/easymde.css",)}
        js = ("js/vendor/easymde.js",)
