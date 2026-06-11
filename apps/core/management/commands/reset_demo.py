"""Drop + reseed the demo database in one shot.

Used by the hourly cron on the public demo server so visitor changes
(renamed orgs, deleted invoices, password changes on the demo user,
etc.) revert on a fixed schedule.

  uv run python manage.py reset_demo                 # confirm + reset
  uv run python manage.py reset_demo --no-input      # for cron jobs

Implementation:
  1. flush — TRUNCATE every Django-managed table (preserves schema).
  2. migrate --run-syncdb — re-apply contenttypes + permissions.
  3. seed_demo — populate users / orders / invoices / kanban / files /…

We deliberately do NOT drop the database itself — that would require
extra Postgres privileges and break production accidentally if
DEMO_MODE was ever flipped off in a real env. flush() is enough.

Safety belt: refuses to run unless settings.DEMO_MODE is True. So if
someone runs this on a non-demo deploy by mistake, it errors out
without touching data.
"""
from __future__ import annotations

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Wipe + reseed the demo database. Refuses to run unless DEMO_MODE=True."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input", action="store_true",
            help="Skip the y/N prompt — for cron usage.",
        )
        parser.add_argument(
            "--force", action="store_true",
            help="Bypass the DEMO_MODE check (use at your own risk).",
        )

    def handle(self, *args, **opts):
        if not getattr(settings, "DEMO_MODE", False) and not opts["force"]:
            raise CommandError(
                "reset_demo refuses to run because DEMO_MODE is False. "
                "Set DEMO_MODE=true in the env, or pass --force to override.",
            )

        if not opts["no_input"]:
            confirm = input(
                "This will WIPE all data in the configured database and "
                "re-seed it from scratch. Type 'reset' to continue: ",
            )
            if confirm.strip() != "reset":
                self.stdout.write(self.style.WARNING("Aborted."))
                return

        self.stdout.write("→ flushing database…")
        call_command("flush", "--no-input")

        self.stdout.write("→ seeding demo data…")
        call_command("seed_demo")

        self.stdout.write(self.style.SUCCESS("✓ demo reset complete"))
