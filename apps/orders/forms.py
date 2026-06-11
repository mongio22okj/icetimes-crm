from django import forms
from django.forms import inlineformset_factory

from .models import Order, OrderItem

BASE = "w-full h-10 rounded-md border border-input bg-background px-3 text-sm"


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["customer", "status"]
        widgets = {
            "customer": forms.Select(attrs={"class": BASE}),
            "status": forms.Select(attrs={"class": BASE}),
        }


OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    fields=["product", "quantity", "unit_price"],
    extra=1,
    can_delete=True,
    widgets={
        "product": forms.Select(attrs={"class": BASE}),
        "quantity": forms.NumberInput(attrs={"class": BASE, "min": "1"}),
        "unit_price": forms.NumberInput(attrs={"class": BASE, "step": "0.01"}),
    },
)
