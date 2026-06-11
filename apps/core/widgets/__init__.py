"""Polished form widgets for Django ModelForm/Form fields.

Public API:

    from apps.core.widgets import (
        FloatingLabelInput, FloatingLabelTextarea,
        IconPrefixInput, IconSuffixInput,
        MultiSelect, TagInput, Combobox,
        RichText, FileDropzone, DateRangePicker,
        TypeaheadMixin,                   # for views that back a Combobox
    )

Each widget subclasses django.forms.Widget and renders via a template
under templates/widgets/<name>.html. Validation states (default / success
/ warning / error) flow from the form's bound state via the shared
_field_wrapper.html partial.

Phase 12 commit 2: scaffolding only. Widgets land in commits 3–6.
The base infrastructure (_base.py) is here so widgets can compose against
a stable foundation when they ship.
"""
from apps.core.widgets._base import (
    SIZE_CLASSES,
    WidgetSize,
    WrappableWidget,
    field_state,
    field_state_classes,
)
from apps.core.widgets.choice import (
    Combobox,
    MultiSelect,
    TagInput,
    TypeaheadMixin,
)
from apps.core.widgets.date import DateRangePicker
from apps.core.widgets.inputs import (
    FloatingLabelInput,
    FloatingLabelTextarea,
    IconPrefixInput,
    IconSuffixInput,
)
from apps.core.widgets.rich import RichText
from apps.core.widgets.upload import FileDropzone

__all__ = [
    "SIZE_CLASSES",
    "WidgetSize",
    "WrappableWidget",
    "field_state",
    "field_state_classes",
    # inputs
    "FloatingLabelInput",
    "FloatingLabelTextarea",
    "IconPrefixInput",
    "IconSuffixInput",
    # choice
    "Combobox",
    "MultiSelect",
    "TagInput",
    "TypeaheadMixin",
    # date + upload
    "DateRangePicker",
    "FileDropzone",
    # rich
    "RichText",
]
