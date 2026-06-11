from django import forms
from django.utils.translation import gettext_lazy as _

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)

DEPOSIT_CHOICES = (
    ("", _("All leads")),
    ("true", _("With deposit")),
    ("false", _("Without deposit")),
)


class LeadFilterForm(forms.Form):
    """Date-range + deposit filter for the external lead list."""

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
    deposit = forms.ChoiceField(
        label=_("Deposit"),
        required=False,
        choices=DEPOSIT_CHOICES,
        widget=forms.Select(attrs={"class": BASE_INPUT}),
    )

    def clean(self):
        cleaned = super().clean()
        date_from, date_to = cleaned.get("date_from"), cleaned.get("date_to")
        if date_from and date_to and date_to < date_from:
            raise forms.ValidationError(_("The end date cannot be before the start date."))
        return cleaned


class LeadSendForm(forms.Form):
    """Manual lead submission towards the external CRM.

    userAgent and ip are filled server-side from the request; the
    remaining required API fields are exposed here.
    """

    phone = forms.RegexField(
        label=_("Phone"),
        regex=r"^\+[1-9]\d{6,14}$",
        error_messages={"invalid": _("Use E.164 format, e.g. +393331234567 (no spaces).")},
        widget=forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "+393331234567"}),
    )
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={"class": BASE_INPUT, "placeholder": "lead@example.com"}),
    )
    name = forms.CharField(
        label=_("First name"),
        max_length=100,
        widget=forms.TextInput(attrs={"class": BASE_INPUT}),
    )
    last_name = forms.CharField(
        label=_("Last name"),
        max_length=100,
        widget=forms.TextInput(attrs={"class": BASE_INPUT}),
    )
    box_id = forms.IntegerField(
        label=_("Box ID"),
        min_value=1,
        widget=forms.NumberInput(attrs={"class": BASE_INPUT, "placeholder": "10"}),
    )
    offer_id = forms.IntegerField(
        label=_("Offer ID (optional)"),
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": BASE_INPUT}),
    )
    country = forms.RegexField(
        label=_("Country (alpha-2)"),
        regex=r"^[A-Za-z]{2}$",
        initial="IT",
        error_messages={"invalid": _("Two-letter code, e.g. IT, GB, DE.")},
        widget=forms.TextInput(attrs={"class": BASE_INPUT, "maxlength": "2"}),
    )
    lang = forms.RegexField(
        label=_("Language (alpha-2)"),
        regex=r"^[A-Za-z]{2}$",
        initial="IT",
        error_messages={"invalid": _("Two-letter code, e.g. IT, EN.")},
        widget=forms.TextInput(attrs={"class": BASE_INPUT, "maxlength": "2"}),
    )

    def to_api_payload(self, request):
        """Build the POST /customer/lead body from cleaned data + request."""
        data = self.cleaned_data
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")
        payload = {
            "phone": data["phone"],
            "email": data["email"],
            "boxId": data["box_id"],
            "name": data["name"],
            "lastName": data["last_name"],
            "userAgent": request.META.get("HTTP_USER_AGENT", "unknown"),
            "ip": ip,
            "country": data["country"].upper(),
            "lang": data["lang"].upper(),
        }
        if data.get("offer_id"):
            payload["offerId"] = data["offer_id"]
        return payload
