from django import forms

from apps.core.widgets import (
    FloatingLabelInput,
    FloatingLabelTextarea,
    IconPrefixInput,
)

from .models import Customer


class CustomerForm(forms.ModelForm):
    """Customer create/edit form using Phase 12 widgets.

    Widgets handle their own size + state plumbing; the surrounding
    template uses {% apex_field %} for the label/error wrapper.
    """

    class Meta:
        model = Customer
        fields = (
            "name", "email", "phone", "company", "avatar",
            "address", "city", "country", "status", "notes",
        )
        widgets = {
            "name":    FloatingLabelInput(floating_label="Name"),
            "email":   IconPrefixInput(icon="mail",
                                       attrs={"type": "email",
                                              "placeholder": "you@example.com"}),
            "phone":   FloatingLabelInput(floating_label="Phone"),
            "company": FloatingLabelInput(floating_label="Company"),
            "address": FloatingLabelInput(floating_label="Street"),
            "city":    FloatingLabelInput(floating_label="City"),
            "country": FloatingLabelInput(floating_label="Country"),
            "notes":   FloatingLabelTextarea(
                floating_label="Notes", rows=4, max_rows=12,
                max_length_counter=True,
                attrs={"maxlength": "2000"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Avatar uses Django's default ClearableFileInput; nudge it into the
        # same visual style as the rest by adding a small class.
        self.fields["avatar"].widget.attrs.setdefault("class", "block text-sm")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = Customer.all_objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A customer with that email already exists.")
        return email
