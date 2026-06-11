from django import forms
from django.contrib.auth import get_user_model

from apps.core.widgets import (
    Combobox,
    FloatingLabelInput,
    FloatingLabelTextarea,
)
from apps.mail.models import Message

User = get_user_model()


class ComposeForm(forms.ModelForm):
    """New message form. Phase 12 widgets — Combobox for recipient,
    floating-label input for subject, auto-grow textarea for body.
    """

    class Meta:
        model = Message
        fields = ["recipient", "subject", "body"]
        widgets = {
            "recipient": Combobox(placeholder="Search recipients…"),
            "subject":   FloatingLabelInput(floating_label="Subject"),
            "body":      FloatingLabelTextarea(
                floating_label="Write your message…",
                rows=8, max_rows=20,
                max_length_counter=True,
                attrs={"maxlength": "10000"},
            ),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(is_staff=True, is_active=True)
        if current_user is not None:
            qs = qs.exclude(pk=current_user.pk)
        self.fields["recipient"].queryset = qs.order_by("username")
        self.fields["recipient"].empty_label = "Select recipient…"


class ReplyForm(forms.Form):
    """Reply form — body only; subject + recipient inferred from parent."""

    body = forms.CharField(
        widget=FloatingLabelTextarea(
            floating_label="Type your reply…",
            rows=5, max_rows=15,
            max_length_counter=True,
            attrs={"maxlength": "10000"},
        ),
    )
