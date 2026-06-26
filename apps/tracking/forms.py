from django import forms

from .models import TrackboxBroker

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)


class TrackboxBrokerForm(forms.ModelForm):
    class Meta:
        model = TrackboxBroker
        fields = (
            "name", "base_url", "username", "password",
            "push_key", "pull_key", "ai", "ci", "gi", "is_active",
        )
        widgets = {
            "password": forms.PasswordInput(render_value=True),
            "base_url": forms.URLInput(attrs={
                "placeholder": "https://track.fintechgurus.org"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "h-4 w-4 rounded border-input")
            else:
                widget.attrs.setdefault("class", BASE_INPUT)
