"""Drop SessionMetadata rows whose underlying Session is gone.

Runs daily in production. Django's session cleanup
(`python manage.py clearsessions`) drops the Session rows; this command
drops the matching SessionMetadata so the Sessions settings pane doesn't
show ghost devices.
"""
from django.core.management.base import BaseCommand

from apps.accounts.middleware import cleanup_orphan_session_metadata


class Command(BaseCommand):
    help = "Drop SessionMetadata rows whose Session no longer exists."

    def handle(self, *args, **options):
        n = cleanup_orphan_session_metadata()
        self.stdout.write(self.style.SUCCESS(f"Dropped {n} orphan session-metadata row(s)."))
