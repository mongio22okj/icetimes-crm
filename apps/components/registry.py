"""Registry of every UI primitive shipped under /components/.

Each PRIMITIVES entry drives:
  - the index page card
  - the detail page lookup (slug → templates/components/pages/<slug>.html)
  - the command palette keyword search

Adding a primitive: append a Primitive(...) entry, then create the
matching templates/components/pages/<slug>.html. Tests assert that
every entry has a backing template.
"""
from dataclasses import dataclass, field

CATEGORIES: tuple[tuple[str, str], ...] = (
    ("overlay", "Overlay"),
    ("disclosure", "Disclosure"),
    ("inputs", "Inputs"),
    ("choice", "Choice"),
    ("upload", "Upload"),
    ("feedback", "Feedback"),
    ("identity", "Identity"),
)


@dataclass(frozen=True)
class Primitive:
    slug: str
    label: str
    category: str       # must be one of CATEGORIES keys
    icon: str           # lucide icon name (rendered via {% icon %} tag)
    description: str    # one-line for the index card
    keywords: tuple[str, ...] = field(default_factory=tuple)


PRIMITIVES: tuple[Primitive, ...] = (
    # ── Overlay ────────────────────────────────────────────────────────
    Primitive("modal", "Modal", "overlay", "square-stack",
              "Centered dialog with backdrop and focus trap.",
              keywords=("dialog", "popup", "lightbox")),
    Primitive("drawer", "Drawer", "overlay", "panel-right",
              "Slide-in panel from any edge.",
              keywords=("offcanvas", "sidebar", "panel")),
    Primitive("toast", "Toast", "overlay", "bell",
              "Transient feedback bound to Django messages.",
              keywords=("snackbar", "notification", "alert")),
    Primitive("tooltip", "Tooltip", "overlay", "info",
              "Small label that appears on hover or focus.",
              keywords=("hint", "label")),
    Primitive("popover", "Popover", "overlay", "message-square",
              "Anchored container for menus, info, or small forms.",
              keywords=("menu", "dropdown")),

    # ── Disclosure ─────────────────────────────────────────────────────
    Primitive("tabs", "Tabs", "disclosure", "layout",
              "Switch between related panels.",
              keywords=("tab", "panel")),
    Primitive("accordion", "Accordion", "disclosure", "chevrons-up-down",
              "Collapsible sections; single or multi-open.",
              keywords=("collapse", "expand", "faq")),
    Primitive("stepper", "Stepper", "disclosure", "list-ordered",
              "Numbered or vertical progress through stages.",
              keywords=("steps", "wizard", "progress")),

    # ── Inputs (preview only — full widgets land in Phase 12) ──────────
    Primitive("datepicker", "Datepicker", "inputs", "calendar",
              "Pick a single date.", keywords=("date", "calendar")),
    Primitive("daterange", "Date range", "inputs", "calendar-range",
              "Pick a start + end date with presets.",
              keywords=("date", "range")),
    Primitive("timepicker", "Timepicker", "inputs", "clock",
              "Pick a time, 12h or 24h.", keywords=("time", "clock")),
    Primitive("colorpicker", "Color picker", "inputs", "palette",
              "Pick a color via swatches or hex.",
              keywords=("color", "palette", "swatch")),

    # ── Choice ─────────────────────────────────────────────────────────
    Primitive("multiselect", "Multi-select", "choice", "list-checks",
              "Tag-style chips inside a single field.",
              keywords=("select", "tags")),
    Primitive("taginput", "Tag input", "choice", "tag",
              "Free-form tags with paste-to-split.",
              keywords=("tags", "labels")),
    Primitive("combobox", "Combobox", "choice", "search",
              "Typeahead from URL endpoint or static list.",
              keywords=("autocomplete", "typeahead")),
    Primitive("toggle-group", "Toggle group", "choice", "toggle-right",
              "Pick one or many from a row of buttons.",
              keywords=("toggle", "buttons")),
    Primitive("segmented", "Segmented control", "choice", "layout",
              "iOS-style segmented switcher.",
              keywords=("segment", "switch", "tabs")),
    Primitive("rating", "Rating", "choice", "star",
              "Stars or hearts for scoring.",
              keywords=("stars", "score", "review")),
    Primitive("slider", "Slider", "choice", "sliders-horizontal",
              "Single value or range selection along an axis.",
              keywords=("range", "value")),

    # ── Upload ─────────────────────────────────────────────────────────
    Primitive("dropzone", "File dropzone", "upload", "upload-cloud",
              "Drag-drop multi-file uploader with previews.",
              keywords=("upload", "file", "drop")),

    # ── Feedback ───────────────────────────────────────────────────────
    Primitive("skeleton", "Skeleton", "feedback", "menu",
              "Shimmering placeholder while content loads.",
              keywords=("loading", "placeholder")),
    Primitive("spinner", "Spinner", "feedback", "loader-circle",
              "Indeterminate progress spinner.",
              keywords=("loading", "progress")),
    Primitive("progress-ring", "Progress ring", "feedback", "target",
              "Circular progress indicator.",
              keywords=("progress", "ring", "donut")),
    Primitive("empty-state", "Empty state", "feedback", "inbox",
              "Standard layouts for no-data, no-results, errors.",
              keywords=("empty", "blank", "zero")),

    # ── Identity ───────────────────────────────────────────────────────
    Primitive("avatar", "Avatar", "identity", "user-circle",
              "Image, initials, status dot, group stack.",
              keywords=("user", "image", "initials")),
    Primitive("badge", "Badge", "identity", "badge",
              "Pill or square label for status and counts.",
              keywords=("pill", "tag", "label", "chip")),
)


def get_primitive(slug: str) -> Primitive | None:
    """Return the Primitive with the given slug, or None."""
    for p in PRIMITIVES:
        if p.slug == slug:
            return p
    return None


def grouped() -> list[dict]:
    """Return primitives grouped by category, in CATEGORIES order.

    Shape: [{"key": "overlay", "label": "Overlay", "items": [Primitive, ...]}, ...]
    Categories with no primitives are skipped (so the page doesn't render
    empty headers if registry shrinks).
    """
    by_key: dict[str, list[Primitive]] = {}
    for p in PRIMITIVES:
        by_key.setdefault(p.category, []).append(p)
    out: list[dict] = []
    for key, label in CATEGORIES:
        items = by_key.get(key)
        if not items:
            continue
        out.append({"key": key, "label": label, "items": items})
    return out
