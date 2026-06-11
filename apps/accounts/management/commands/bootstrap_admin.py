"""Create or update the production admin user from environment variables.

Idempotent — safe to run on every build/boot. No-op when ADMIN_USERNAME
or ADMIN_PASSWORD are unset, so dev environments are unaffected.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Create/update the admin user from the ADMIN_USERNAME, "
        "ADMIN_EMAIL and ADMIN_PASSWORD environment variables."
    )

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        email = os.environ.get("ADMIN_EMAIL", "").strip()
        if not username or not password:
            self.stdout.write("ADMIN_USERNAME/ADMIN_PASSWORD not set — skipping.")
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email or f"{username}@localhost"},
        )
        if email:
            user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.role = "admin"
        if not user.email_verified_at:
            user.email_verified_at = timezone.now()
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"Admin user '{username}' {'created' if created else 'updated'}."
        ))
