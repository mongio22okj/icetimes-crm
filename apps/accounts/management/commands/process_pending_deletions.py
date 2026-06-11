"""Hard-delete accounts whose grace period has elapsed.

Runs nightly in production (cron / scheduled task). Idempotent — safe
to re-run; only deletes users where:

  - `pending_deletion_at` is set, AND
  - `pending_deletion_at + GRACE_PERIOD_DAYS < now()`

Use `--grace-days N` to override the grace window (default 30) for
testing or custom retention policies.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

GRACE_PERIOD_DAYS = 30


class Command(BaseCommand):
    help = "Hard-delete accounts whose deletion grace period has elapsed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--grace-days", type=int, default=GRACE_PERIOD_DAYS,
            help="Days after request before hard delete (default 30).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print what would be deleted without doing it.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        cutoff = timezone.now() - timedelta(days=options["grace_days"])
        qs = User.objects.filter(pending_deletion_at__isnull=False,
                                 pending_deletion_at__lt=cutoff)
        n = qs.count()
        if not n:
            self.stdout.write("No accounts past their grace period.")
            return
        for user in qs:
            self.stdout.write(
                f"{'DRY RUN — would delete' if options['dry_run'] else 'Deleting'} "
                f"{user.username} (requested {user.pending_deletion_at.date()})",
            )
        if not options["dry_run"]:
            qs.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {n} account(s)."))
