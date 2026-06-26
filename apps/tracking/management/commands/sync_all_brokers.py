"""Sync stati lead da tutti i broker pull-capable (TrackBox + SPM Monster).

Pensato per il cron (ogni 10 min). IREV è escluso: i suoi stati arrivano
via postback.
"""
from django.core.management.base import BaseCommand

from apps.tracking.sync import sync_all_pullable


class Command(BaseCommand):
    help = "Aggiorna gli stati dei lead via pull da TrackBox + SPM Monster."

    def handle(self, *args, **options):
        r = sync_all_pullable()
        self.stdout.write(
            f"Sync: {r['updated']} aggiornati, {r['matched']} agganciati, "
            f"{r['seen']} righe lette, {r['brokers']} broker.")
        for err in r["errors"]:
            self.stderr.write(f"  errore: {err}")
