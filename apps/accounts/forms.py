from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import UserCreationForm

from .models import User

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_INPUT)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_INPUT)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "role", "bio", "avatar")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in ("bio", "avatar"):
                field.widget.attrs.setdefault("class", BASE_INPUT)
        self.fields["bio"].widget = forms.Textarea(
            attrs={"class": BASE_INPUT.replace("h-10", "min-h-[120px] py-2"), "rows": 4}
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email


class ProfileForm(forms.ModelForm):
    """Profile edit form using Phase 12 widgets.

    Email gets an icon-prefixed input; bio uses an auto-grow textarea
    with character counter. Other fields stay floating-label by default.
    """

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "bio", "avatar")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.widgets import (
            FloatingLabelInput,
            FloatingLabelTextarea,
            IconPrefixInput,
        )
        self.fields["first_name"].widget = FloatingLabelInput(floating_label="First name")
        self.fields["last_name"].widget = FloatingLabelInput(floating_label="Last name")
        self.fields["email"].widget = IconPrefixInput(
            icon="mail", attrs={"type": "email", "placeholder": "you@example.com"},
        )
        self.fields["bio"].widget = FloatingLabelTextarea(
            floating_label="Bio", rows=4, max_rows=12,
            max_length_counter=True, attrs={"maxlength": "500"},
        )
        # Avatar: keep Django's default file input visual.
        self.fields["avatar"].widget.attrs.setdefault("class", "block text-sm")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email


class StyledPasswordChangeForm(DjangoPasswordChangeForm):
    """Django's PasswordChangeForm with BASE_INPUT classes applied."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_INPUT)


class TwoFactorSetupForm(forms.Form):
    code = forms.CharField(
        max_length=6, min_length=6,
        widget=forms.TextInput(attrs={
            "class": BASE_INPUT + " font-mono tracking-widest text-center",
            "inputmode": "numeric",
            "autocomplete": "one-time-code",
            "placeholder": "123456",
        }),
    )


class PasswordConfirmForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": BASE_INPUT,
            "autocomplete": "current-password",
            "placeholder": "Your password",
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        pw = self.cleaned_data["password"]
        if authenticate(username=self.user.username, password=pw) is None:
            raise forms.ValidationError("Incorrect password.")
        return pw


class TwoFactorChallengeForm(forms.Form):
    code = forms.CharField(
        max_length=12,  # accommodates "XXXXX-XXXXX" (11) + safety
        widget=forms.TextInput(attrs={
            "class": BASE_INPUT + " font-mono tracking-widest text-center",
            "autocomplete": "one-time-code",
            "inputmode": "text",
            "placeholder": "123456 or recovery code",
        }),
    )
