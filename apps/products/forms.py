from django import forms

from .models import Product

BASE_INPUT = "w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
BASE_TEXTAREA = "w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[120px]"


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "slug", "sku", "price", "stock", "status", "category", "description", "image"]
        widgets = {
            "name": forms.TextInput(attrs={"class": BASE_INPUT}),
            "slug": forms.TextInput(attrs={"class": BASE_INPUT}),
            "sku": forms.TextInput(attrs={"class": BASE_INPUT}),
            "price": forms.NumberInput(attrs={"class": BASE_INPUT, "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"class": BASE_INPUT}),
            "status": forms.Select(attrs={"class": BASE_INPUT}),
            "category": forms.Select(attrs={"class": BASE_INPUT}),
            "description": forms.Textarea(attrs={"class": BASE_TEXTAREA}),
        }
