from django import forms

from .models import IrevBroker, Lead, SpmMonsterBroker, TrackboxBroker

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)


def _style_broker_fields(form):
    """Applica le classi Tailwind ai campi dei form broker (input/checkbox/textarea)."""
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "h-4 w-4 rounded border-input")
        elif isinstance(widget, forms.Textarea):
            widget.attrs.setdefault(
                "class",
                BASE_INPUT.replace("h-10", "min-h-[260px] py-2 font-mono text-xs"))
        else:
            widget.attrs.setdefault("class", BASE_INPUT)


class TrackboxBrokerForm(forms.ModelForm):
    class Meta:
        model = TrackboxBroker
        fields = (
            "name", "base_url", "username", "password",
            "push_key", "pull_key", "ai", "ci", "gi",
            "funnel", "landing_slug", "note", "landing_html", "is_active",
        )
        widgets = {
            "password": forms.PasswordInput(render_value=True),
            "base_url": forms.URLInput(attrs={
                "placeholder": "https://track.fintechgurus.org"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class IrevBrokerForm(forms.ModelForm):
    class Meta:
        model = IrevBroker
        fields = (
            "name", "base_url", "token", "affiliate_id", "offer_id",
            "goal_lead_uuid", "goal_ftd_uuid", "funnel", "landing_slug", "note",
            "landing_html", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={"placeholder": "https://stylishwnt.com"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class SpmMonsterBrokerForm(forms.ModelForm):
    class Meta:
        model = SpmMonsterBroker
        fields = (
            "name", "base_url", "api_key", "affc", "bxc", "vtc",
            "funnel", "landing_slug", "note", "landing_html", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={"placeholder": "https://spmteamone.it.com"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class LandingLeadForm(forms.ModelForm):
    """Form pubblico della landing: i dati che il visitatore inserisce."""

    class Meta:
        model = Lead
        fields = ("firstname", "lastname", "email", "phone", "country")
        widgets = {
            "firstname": forms.TextInput(attrs={"placeholder": "Nome"}),
            "lastname": forms.TextInput(attrs={"placeholder": "Cognome"}),
            "email": forms.EmailInput(attrs={"placeholder": "tua@email.com"}),
            "phone": forms.TextInput(attrs={"placeholder": "+39 333 1234567"}),
            "country": forms.TextInput(attrs={"placeholder": "IT", "maxlength": "2"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["firstname"].required = True
        self.fields["email"].required = True
        self.fields["phone"].required = True
        self.fields["country"].initial = "IT"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_INPUT)

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_country(self):
        return (self.cleaned_data.get("country") or "IT").strip().upper()[:2]
