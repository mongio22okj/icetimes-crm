"""Date and date-range widgets.

DateRangePicker stores a single comma-joined `"from,to"` string under
the field name. Backs a `forms.CharField` directly, or a custom field
that splits the value into two `date` objects on clean.

Usage:

    class FilterForm(forms.Form):
        period = forms.CharField(
            required=False,
            widget=DateRangePicker(),
        )

        def clean_period(self):
            raw = self.cleaned_data["period"] or ""
            parts = [p.strip() for p in raw.split(",")]
            if len(parts) == 2 and parts[0] and parts[1]:
                from datetime import date
                try:
                    return (date.fromisoformat(parts[0]), date.fromisoformat(parts[1]))
                except ValueError:
                    raise forms.ValidationError("Invalid date.")
            return None

The widget itself shows a button-style trigger displaying the range,
opens a popover with two side-by-side date inputs and preset shortcuts.
Full keyboard navigation (Tab through date inputs, Esc closes).
"""
from __future__ import annotations

from django import forms

from apps.core.widgets._base import WrappableWidget


class DateRangePicker(WrappableWidget, forms.Widget):
    """Date range picker — stores `"YYYY-MM-DD,YYYY-MM-DD"` under the field.

    Args:
        size: sm | md | lg (default md)
        helper: text below
        with_presets: when True, render preset shortcut buttons (Today,
                      Last 7 days, etc.) above the custom range inputs
        attrs: passed through to the trigger button
    """
    template_name = "widgets/date_range_picker.html"

    def __init__(self, *, with_presets: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.with_presets = with_presets

    def value_from_datadict(self, data, files, name):
        return data.get(name, "")

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        from_value, to_value = self._parse(value)
        ctx["widget"].update({
            "from_value": from_value,
            "to_value": to_value,
            "with_presets": self.with_presets,
        })
        return ctx

    @staticmethod
    def _parse(value) -> tuple[str, str]:
        """Parse the stored value into two ISO date strings.

        Accepts: "from,to", "from", "", a tuple/list of two values, or
        a tuple/list of two `date` objects (for initial=...).
        """
        if value is None or value == "":
            return "", ""
        if isinstance(value, list | tuple):
            from_v = str(value[0]) if len(value) >= 1 and value[0] else ""
            to_v = str(value[1]) if len(value) >= 2 and value[1] else ""
            return from_v, to_v
        parts = [p.strip() for p in str(value).split(",")]
        from_v = parts[0] if parts else ""
        to_v = parts[1] if len(parts) > 1 else ""
        return from_v, to_v
