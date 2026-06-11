from django import forms
from django.forms import inlineformset_factory

from apps.invoices.models import Invoice, InvoiceItem

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["customer", "order", "issue_date", "due_date", "tax_rate", "notes"]
        widgets = {
            "customer":   forms.Select(attrs={"class": BASE_INPUT}),
            "order":      forms.Select(attrs={"class": BASE_INPUT}),
            "issue_date": forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "due_date":   forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "tax_rate":   forms.NumberInput(attrs={"class": BASE_INPUT, "step": "0.01", "min": 0}),
            "notes":      forms.Textarea(attrs={
                "class": BASE_INPUT.replace("h-10", "min-h-[120px] py-2"),
                "rows": 3,
            }),
        }

    def clean(self):
        cleaned = super().clean()
        issue = cleaned.get("issue_date")
        due = cleaned.get("due_date")
        if issue and due and due < issue:
            raise forms.ValidationError("Due date cannot be before issue date.")
        return cleaned


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    fields=["description", "quantity", "unit_price"],
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
    widgets={
        "description": forms.TextInput(attrs={"class": BASE_INPUT}),
        "quantity":    forms.NumberInput(attrs={"class": BASE_INPUT, "min": 1}),
        "unit_price":  forms.NumberInput(attrs={"class": BASE_INPUT, "step": "0.01", "min": 0}),
    },
)
