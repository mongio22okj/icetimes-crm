from django import forms
from django.contrib.auth import get_user_model

from apps.kanban.models import Card

User = get_user_model()

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)
TEXTAREA = BASE_INPUT.replace("h-10", "min-h-[120px] py-2")


class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ["title", "description", "status", "priority", "assignee", "due_date"]
        widgets = {
            "title":       forms.TextInput(attrs={"class": BASE_INPUT}),
            "description": forms.Textarea(attrs={"class": TEXTAREA, "rows": 3}),
            "status":      forms.Select(attrs={"class": BASE_INPUT}),
            "priority":    forms.Select(attrs={"class": BASE_INPUT}),
            "assignee":    forms.Select(attrs={"class": BASE_INPUT}),
            "due_date":    forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = User.objects.filter(
            is_staff=True, is_active=True,
        ).order_by("username")
        self.fields["assignee"].empty_label = "Unassigned"
