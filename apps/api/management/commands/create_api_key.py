"""Create an APIKey for a user from the command line.

Usage:
    uv run python manage.py create_api_key demo --name "Local dev"

Prints the raw key once — copy it immediately, you won't see it again.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.api.models import APIKey

User = get_user_model()


class Command(BaseCommand):
    help = "Create an APIKey for a given user. Prints the raw key once."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Username of the key owner.")
        parser.add_argument("--name", default="cli", help="Label for the key.")

    def handle(self, *args, **options):
        username = options["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as e:
            raise CommandError(f"No user with username {username!r}") from e
        instance, raw = APIKey.generate(user, options["name"])
        self.stdout.write(self.style.SUCCESS(
            f"Created APIKey id={instance.pk} prefix={instance.key_prefix} for {user.username}.",
        ))
        self.stdout.write("")
        self.stdout.write("Raw key (shown once — copy now):")
        self.stdout.write(self.style.WARNING(raw))
        self.stdout.write("")
        self.stdout.write("Use it via:")
        self.stdout.write(f"  curl -H 'Authorization: Bearer {raw}' http://localhost:8000/api/v1/customers/")
