from django import forms
from django.utils.translation import gettext_lazy as _

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)

PULL_TYPE_CHOICES = (
    ("3", _("Leads + deposits")),
    ("2", _("Leads only")),
    ("4", _("Deposits only")),
)


class LeadFilterForm(forms.Form):
    """Date-range + type filter for the TrackBox pull API."""

    date_from = forms.DateField(
        label=_("From"),
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
    )
    date_to = forms.DateField(
        label=_("To"),
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
    )
    pull_type = forms.ChoiceField(
        label=_("Type"),
        required=False,
        choices=PULL_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": BASE_INPUT}),
    )

    def clean(self):
        cleaned = super().clean()
        date_from, date_to = cleaned.get("date_from"), cleaned.get("date_to")
        if date_from and date_to and date_to < date_from:
            raise forms.ValidationError(_("The end date cannot be before the start date."))
        return cleaned


class LeadSendForm(forms.Form):
    """Manual lead submission towards TrackBox (/api/signup/procform).

    ai/ci/gi come from settings; userip is filled server-side from the
    request. The remaining fields are exposed here.
    """

    firstname = forms.CharField(
        label=_("First name"),
        max_length=100,
        widget=forms.TextInput(attrs={"class": BASE_INPUT}),
    )
    lastname = forms.CharField(
        label=_("Last name"),
        max_length=100,
        widget=forms.TextInput(attrs={"class": BASE_INPUT}),
    )
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={"class": BASE_INPUT, "placeholder": "lead@example.com"}),
    )
    phone = forms.RegexField(
        label=_("Phone"),
        regex=r"^\+[1-9]\d{6,14}$",
        error_messages={"invalid": _("Use E.164 format, e.g. +393331234567 (no spaces).")},
        widget=forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "+393331234567"}),
    )
    so = forms.CharField(
        label=_("Funnel / source (so)"),
        required=False,
        max_length=200,
        help_text=_("Funnel name shown in TrackBox reports."),
        widget=forms.TextInput(attrs={"class": BASE_INPUT}),
    )
    lg = forms.RegexField(
        label=_("Language (alpha-2)"),
        regex=r"^[A-Za-z]{2}$",
        initial="IT",
        error_messages={"invalid": _("Two-letter code, e.g. IT, EN.")},
        widget=forms.TextInput(attrs={"class": BASE_INPUT, "maxlength": "2"}),
    )
    sub = forms.CharField(
        label=_("Sub (optional)"),
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": BASE_INPUT}),
    )

    def to_api_payload(self, request, account_password):
        """Build the push body from cleaned data + request context."""
        data = self.cleaned_data
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")
        payload = {
            "firstname": data["firstname"],
            "lastname": data["lastname"],
            "email": data["email"],
            "phone": data["phone"],
            "password": account_password,
            "userip": ip,
            "lg": data["lg"].upper(),
        }
        if data.get("so"):
            payload["so"] = data["so"]
        if data.get("sub"):
            payload["sub"] = data["sub"]
        return payload
