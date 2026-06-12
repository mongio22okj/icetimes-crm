from django import forms
from django.utils.translation import gettext_lazy as _

from .models import LeadSource, Partner
from .sources import push_sources

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)


def source_token(src):
    """Stable form value identifying a source (DB pk or env shim)."""
    return str(src.pk) if getattr(src, "pk", None) else f"env-{src.kind}"


class LeadSendForm(forms.Form):
    """Manual lead submission towards a chosen active source."""

    target = forms.ChoiceField(
        label=_("Send to"),
        choices=(),
        widget=forms.Select(attrs={"class": BASE_INPUT}),
    )
    firstname = forms.CharField(label=_("First name"), max_length=100,
                                widget=forms.TextInput(attrs={"class": BASE_INPUT}))
    lastname = forms.CharField(label=_("Last name"), max_length=100,
                               widget=forms.TextInput(attrs={"class": BASE_INPUT}))
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={"class": BASE_INPUT, "placeholder": "lead@example.com"}))
    phone = forms.RegexField(
        label=_("Phone"), regex=r"^\+[1-9]\d{6,14}$",
        error_messages={"invalid": _("Use E.164 format, e.g. +393331234567 (no spaces).")},
        widget=forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "+393331234567"}))
    country = forms.RegexField(
        label=_("Country (alpha-2)"), regex=r"^[A-Za-z]{2}$", initial="IT",
        error_messages={"invalid": _("Two-letter code, e.g. IT, ES, DE.")},
        widget=forms.TextInput(attrs={"class": BASE_INPUT, "maxlength": "2"}))
    lg = forms.RegexField(
        label=_("Language (alpha-2)"), regex=r"^[A-Za-z]{2}$", initial="IT",
        error_messages={"invalid": _("Two-letter code, e.g. IT, EN.")},
        widget=forms.TextInput(attrs={"class": BASE_INPUT, "maxlength": "2"}))
    so = forms.CharField(label=_("Funnel / source (so)"), required=False, max_length=200,
                         widget=forms.TextInput(attrs={"class": BASE_INPUT}))
    sub = forms.CharField(label=_("Sub (optional)"), required=False, max_length=200,
                          widget=forms.TextInput(attrs={"class": BASE_INPUT}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sources = push_sources()
        self.fields["target"].choices = [
            (source_token(s), f"{s.name} ({s.get_kind_display() if hasattr(s, 'get_kind_display') else s.kind})")
            for s in sources
        ]
        if not sources:
            self.fields["target"].choices = [("", _("No source configured"))]


class LeadSourceForm(forms.ModelForm):
    """Add/edit an external lead API source from the UI."""

    class Meta:
        model = LeadSource
        fields = (
            "name", "kind", "base_url", "is_active", "token",
            "username", "password", "ai", "ci", "gi",
            "affiliate_id", "offer_id", "goal_lead", "goal_ftd",
            "link_id", "funnel", "source_tag", "notes",
        )
        widgets = {
            "password": forms.PasswordInput(render_value=True),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault(
                    "class", BASE_INPUT.replace("h-10", "min-h-[90px] py-2"))
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "h-4 w-4 rounded border-input")
            else:
                widget.attrs.setdefault("class", BASE_INPUT)

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        token = cleaned.get("token")
        if kind and not token:
            self.add_error("token", _("Token / API key è obbligatorio."))
        if kind == LeadSource.KIND_TRACKBOX:
            if not cleaned.get("username") or not cleaned.get("password"):
                raise forms.ValidationError(
                    _("TrackBox richiede username e password."))
        return cleaned


class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = ("slug", "name", "landing_url", "api_key", "note", "is_active")
        widgets = {
            "slug": forms.TextInput(attrs={"placeholder": "mio_partner_1"}),
            "name": forms.TextInput(attrs={"placeholder": "Partner #1"}),
            "landing_url": forms.URLInput(attrs={"placeholder": "https://..."}),
            "api_key": forms.TextInput(attrs={"placeholder": "..."}),
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "Info per te stesso"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "h-4 w-4 rounded border-input")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class",
                                       BASE_INPUT.replace("h-10", "min-h-[90px] py-2"))
            else:
                widget.attrs.setdefault("class", BASE_INPUT)
