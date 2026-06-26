from django import forms

from apps.marketing.models import SupportTicket

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)
TEXTAREA = BASE_INPUT.replace("h-10", "min-h-50 py-2")


class SupportForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["name", "email", "subject", "body"]
        widgets = {
            "name":    forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "Your name"}),
            "email":   forms.EmailInput(attrs={"class": BASE_INPUT, "placeholder": "you@example.com"}),
            "subject": forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "What's this about?"}),
            "body":    forms.Textarea(attrs={"class": TEXTAREA, "rows": 5, "placeholder": "Describe your issue or question…"}),
        }
