from django import forms

from apps.wizard.models import WizardSubmission

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)


class AccountStepForm(forms.Form):
    name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "Your name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": BASE_INPUT, "placeholder": "you@example.com"}))


class CompanyStepForm(forms.Form):
    company = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={"class": BASE_INPUT}))
    role = forms.CharField(max_length=80, required=False, widget=forms.TextInput(attrs={"class": BASE_INPUT}))
    team_size = forms.ChoiceField(
        choices=WizardSubmission.TEAM_SIZE_CHOICES,
        widget=forms.Select(attrs={"class": BASE_INPUT}),
    )


class PreferencesStepForm(forms.Form):
    theme = forms.ChoiceField(
        choices=WizardSubmission.THEME_CHOICES,
        widget=forms.Select(attrs={"class": BASE_INPUT}),
    )
    notifications_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "rounded border-input"}),
    )
