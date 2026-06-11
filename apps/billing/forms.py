from django import forms

from .models import PaymentMethod

BASE_INPUT = (
    "h-10 w-full rounded-md border border-border bg-background px-3 py-2 "
    "text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
)


class PaymentMethodForm(forms.ModelForm):
    class Meta:
        model = PaymentMethod
        fields = ("brand", "last4", "exp_month", "exp_year", "cardholder", "is_default")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_INPUT)
        self.fields["last4"].widget.attrs["maxlength"] = "4"
        self.fields["last4"].widget.attrs["pattern"] = "[0-9]{4}"

    def clean_last4(self):
        v = (self.cleaned_data.get("last4") or "").strip()
        if not (v.isdigit() and len(v) == 4):
            raise forms.ValidationError("Enter the last 4 digits of the card.")
        return v


class BillingEmailForm(forms.Form):
    billing_email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": BASE_INPUT}),
    )
