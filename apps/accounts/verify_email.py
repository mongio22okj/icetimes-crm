"""Token + email helpers for the email-verification flow.

Uses Django's default_token_generator (same primitive behind password reset).
"""
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def build_verify_url(user, request) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return request.build_absolute_uri(
        reverse("email_verify_confirm", kwargs={"uidb64": uidb64, "token": token})
    )


def send_verify_email(user, request) -> None:
    verify_url = build_verify_url(user, request)
    context = {
        "user": user,
        "verify_url": verify_url,
        "site_name": "Apex Dashboard",
        "cta_url": verify_url,
        "cta_label": "Verify email",
    }
    body_txt = render_to_string("registration/email_verify_email.txt", context)
    body_html = render_to_string("registration/email_verify_email.html", context)
    send_mail(
        subject="Verify your Apex Dashboard email",
        message=body_txt,
        from_email=None,  # uses DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
        html_message=body_html,
    )
