import re

from django import forms

from .models import Product

BASE_INPUT = "w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
BASE_TEXTAREA = "w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[120px]"
COLOR_INPUT = "h-10 w-20 rounded-md border border-input bg-background cursor-pointer"


def video_embed_url(url: str) -> str:
    """Convert a YouTube/Vimeo watch URL to its embed URL."""
    if not url:
        return ""
    yt = re.search(r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/|embed/))([A-Za-z0-9_-]{11})", url)
    if yt:
        return f"https://www.youtube.com/embed/{yt.group(1)}"
    vm = re.search(r"vimeo\.com/(\d+)", url)
    if vm:
        return f"https://player.vimeo.com/video/{vm.group(1)}"
    return url


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            # Catalog
            "name", "slug", "sku", "price", "stock", "status", "category",
            "description", "image",
            # Media
            "video_url", "gallery_image_1", "gallery_image_2", "gallery_image_3",
            # Landing
            "badge", "cta_label", "accent_color", "theme",
            "success_message", "redirect_url",
            # Status API
            "status_api_url", "status_api_key",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": BASE_INPUT}),
            "slug": forms.TextInput(attrs={"class": BASE_INPUT}),
            "sku": forms.TextInput(attrs={"class": BASE_INPUT}),
            "price": forms.NumberInput(attrs={"class": BASE_INPUT, "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"class": BASE_INPUT}),
            "status": forms.Select(attrs={"class": BASE_INPUT}),
            "category": forms.Select(attrs={"class": BASE_INPUT}),
            "description": forms.Textarea(attrs={"class": BASE_TEXTAREA}),
            "video_url": forms.URLInput(attrs={"class": BASE_INPUT,
                                               "placeholder": "https://youtu.be/… oppure https://vimeo.com/…"}),
            "badge": forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "🔥 OFFERTA LIMITATA"}),
            "cta_label": forms.TextInput(attrs={"class": BASE_INPUT}),
            "accent_color": forms.TextInput(attrs={"type": "color", "class": COLOR_INPUT}),
            "theme": forms.Select(attrs={"class": BASE_INPUT}),
            "success_message": forms.TextInput(attrs={"class": BASE_INPUT}),
            "redirect_url": forms.URLInput(attrs={"class": BASE_INPUT,
                                                   "placeholder": "https://… (lascia vuoto per mostrare solo il messaggio)"}),
            "status_api_url": forms.URLInput(attrs={"class": BASE_INPUT,
                                                     "placeholder": "https://…/api/sale-status"}),
            "status_api_key": forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "..."}),
        }
