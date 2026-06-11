from django import forms

from apps.events.models import Event

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)
TEXTAREA = BASE_INPUT.replace("h-10", "min-h-[120px] py-2")


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["title", "description", "start", "end", "all_day", "category"]
        widgets = {
            "title":       forms.TextInput(attrs={"class": BASE_INPUT}),
            "description": forms.Textarea(attrs={"class": TEXTAREA, "rows": 3}),
            "start":       forms.DateTimeInput(attrs={"type": "datetime-local", "class": BASE_INPUT}),
            "end":         forms.DateTimeInput(attrs={"type": "datetime-local", "class": BASE_INPUT}),
            "all_day":     forms.CheckboxInput(attrs={"class": "rounded border-input"}),
            "category":    forms.Select(attrs={"class": BASE_INPUT}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start")
        end = cleaned.get("end")
        if start and end and end < start:
            raise forms.ValidationError("End must be after start.")
        return cleaned
