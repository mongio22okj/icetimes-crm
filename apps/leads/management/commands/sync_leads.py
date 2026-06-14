"""Management command: python manage.py sync_leads [--dry-run]"""
from django.core.management.base import BaseCommand

from apps.leads.services import run_sync


class Command(BaseCommand):
    help = "Sincronizza leads da tutte le sorgenti attive (IREV, TrackBox, Affinitrax)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula la sync senza scrivere sul database",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        self.stdout.write(f"Avvio sync (dry_run={dry_run})...")

        result = run_sync(dry_run=dry_run)

        for line in result["ok"]:
            self.stdout.write(self.style.SUCCESS(f"  ✓ {line}"))
        for line in result["errors"]:
            self.stderr.write(self.style.ERROR(f"  ✗ {line}"))

        self.stdout.write(f"Audit ID: {result['audit_id']}")
        self.stdout.write(self.style.SUCCESS("Sync completata."))
