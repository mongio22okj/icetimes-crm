from django import forms

from .models import (IrevBroker, Lead, SpmMonsterBroker, TrackboxBroker,
                     TYourAdsBroker, GalassiaBroker, OpenAffBroker,
                     GlobalTradeBroker, OneCryptBroker, CpaForgeBroker,
                     AffinitraxBroker, LeadShakerBroker)

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
            "push_key", "pull_key", "ai", "ci", "gi", "extra_params",
            "funnel", "landing_slug", "landing_brand", "note", "landing_html",
            "match_by_contact", "is_active",
        )
        widgets = {
            "password": forms.PasswordInput(render_value=True),
            "base_url": forms.URLInput(attrs={
                "placeholder": "https://track.fintechgurus.org"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
            "extra_params": forms.Textarea(attrs={
                "rows": 3,
                "class": BASE_INPUT.replace("h-10", "min-h-[70px] py-2 font-mono text-xs"),
                "placeholder": '{"MPC_7": "LIVE", "MPC_8": "59704"}'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class IrevBrokerForm(forms.ModelForm):
    class Meta:
        model = IrevBroker
        fields = (
            "name", "base_url", "token", "affiliate_id", "offer_id",
            "goal_lead_uuid", "goal_ftd_uuid", "funnel", "landing_slug", "landing_brand", "note",
            "landing_html", "api_path", "extra_params", "use_pull", "is_active",
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
            "funnel", "landing_slug", "landing_brand", "note", "landing_html",
            "match_by_contact", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={"placeholder": "https://spmteamone.it.com"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class LandingLeadForm(forms.ModelForm):
    """Form pubblico della landing: i dati che il visitatore inserisce.

    Antifrode: campo honeypot `hp_url` (nascosto). Se valorizzato → è un bot,
    il form viene scartato.
    """

    # Honeypot: nascosto agli umani, riempito spesso dai bot.
    hp_url = forms.CharField(required=False, label="",
                             widget=forms.HiddenInput(attrs={
                                 "autocomplete": "off", "tabindex": "-1"}))

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

    def clean_phone(self):
        import re
        phone = (self.cleaned_data.get("phone") or "").strip()
        digits = re.sub(r"\D", "", phone)
        if len(digits) < 7 or len(digits) > 15:
            raise forms.ValidationError("Numero di telefono non valido.")
        return phone

    def clean(self):
        cleaned = super().clean()
        if (cleaned.get("hp_url") or "").strip():
            # Honeypot riempito → bot. Scartiamo senza dettagli.
            raise forms.ValidationError("Invio non valido.")
        return cleaned


class TYourAdsBrokerForm(forms.ModelForm):
    class Meta:
        model = TYourAdsBroker
        fields = (
            "name", "base_url", "api_key", "offer_name", "offer_website",
            "landing_slug", "landing_brand", "note", "landing_html",
            "match_by_contact", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={"placeholder": "https://tyourads-api.com"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class GalassiaBrokerForm(forms.ModelForm):
    class Meta:
        model = GalassiaBroker
        fields = (
            "name", "base_url", "api_token", "link_id", "funnel", "source",
            "country", "language", "landing_slug", "landing_brand", "note",
            "landing_html", "match_by_contact", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={"placeholder": "https://elnopy.crypto-galassia.com"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class OpenAffBrokerForm(forms.ModelForm):
    class Meta:
        model = OpenAffBroker
        fields = (
            "name", "base_url", "api_path", "pull_url", "token", "aff_id",
            "offer_id", "funnel",
            "landing_slug", "landing_brand", "note", "landing_html",
            "match_by_contact", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={"placeholder": "http://vip.kofoboo.com"}),
            "api_path": forms.TextInput(attrs={"placeholder": "/api"}),
            "token": forms.Textarea(attrs={"rows": 3}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class GlobalTradeBrokerForm(forms.ModelForm):
    class Meta:
        model = GlobalTradeBroker
        fields = (
            "name", "base_url", "token", "user_id", "source", "funnel",
            "landing_domain", "landing_slug", "landing_brand", "note",
            "landing_html", "match_by_contact", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={
                "placeholder": "https://crm.globaltrade-company.live"}),
            "token": forms.Textarea(attrs={"rows": 3}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class OneCryptBrokerForm(forms.ModelForm):
    class Meta:
        model = OneCryptBroker
        fields = (
            "name", "base_url", "key", "web_id", "offer_id", "funnel",
            "landing_slug", "landing_brand", "note", "landing_html",
            "match_by_contact", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={
                "placeholder": "http://api.onecrypt.link"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class CpaForgeBrokerForm(forms.ModelForm):
    class Meta:
        model = CpaForgeBroker
        fields = (
            "name", "base_url", "key", "offer_name", "funnel",
            "landing_slug", "landing_brand", "note", "landing_html",
            "match_by_contact", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={
                "placeholder": "https://cpfrg-api.com"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class AffinitraxBrokerForm(forms.ModelForm):
    class Meta:
        model = AffinitraxBroker
        fields = (
            "name", "base_url", "api_key", "funnel",
            "landing_slug", "landing_brand", "note", "landing_html",
            "match_by_contact", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={
                "placeholder": "https://affinitrax.com"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)


class LeadShakerBrokerForm(forms.ModelForm):
    class Meta:
        model = LeadShakerBroker
        fields = (
            "name", "base_url", "token", "user_id", "source", "funnel",
            "landing_slug", "landing_brand", "note", "landing_html",
            "match_by_contact", "is_active",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={
                "placeholder": "https://crm.lead-shaker.live"}),
            "landing_html": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_broker_fields(self)
