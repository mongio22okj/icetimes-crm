from django import forms

from apps.marketing.models import LandingPage, SupportTicket

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


class LandingPageForm(forms.ModelForm):
    class Meta:
        model = LandingPage
        fields = (
            "slug", "title", "subtitle", "badge", "cta_label",
            "theme", "accent_color", "form_variant",
            "funnel", "source_tag", "sub",
            "success_message", "redirect_url",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "h-4 w-4 rounded border-input")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", TEXTAREA)
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", BASE_INPUT)
            else:
                widget.attrs.setdefault("class", BASE_INPUT)
        # Show accent_color as a native color picker.
        self.fields["accent_color"].widget = forms.TextInput(attrs={
            "type": "color",
            "class": "h-10 w-20 rounded-md border border-input bg-background cursor-pointer",
        })
