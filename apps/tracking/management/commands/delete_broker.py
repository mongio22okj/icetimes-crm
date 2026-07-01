"""Cancella un broker e TUTTO cio' che gli appartiene: i suoi lead e i push log
di quei lead. Operazione irreversibile, quindi:

  * default = DRY-RUN: mostra solo cosa verrebbe cancellato, non tocca nulla;
  * serve --yes per eseguire davvero (tutto dentro una transazione).

Nota: le 5 tabelle broker hanno PK separate, quindi "17" da solo puo' essere
ambiguo. Usa --list per vedere tutti i broker, oppure passa --kind per essere
esplicito. Con solo --id, se il pk esiste in piu' tabelle il comando si ferma
e ti chiede di specificare --kind.

Esempi:
  python manage.py delete_broker --list
  python manage.py delete_broker --id 17                 # dry-run
  python manage.py delete_broker --kind irev --id 17 --yes
  python manage.py delete_broker --id 17 --keep-leads --yes   # cancella solo il broker
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.tracking.models import (
    BROKER_MODELS,
    Lead,
    PushLog,
    broker_by_kind,
)

_KINDS = {m.kind: m for m in BROKER_MODELS}


class Command(BaseCommand):
    help = ("Cancella un broker e (di default) tutti i suoi lead + push log. "
            "Dry-run se manca --yes.")

    def add_arguments(self, parser):
        parser.add_argument("--list", action="store_true",
                            help="Elenca tutti i broker (kind:pk, nome, lead) ed esci.")
        parser.add_argument("--kind", choices=sorted(_KINDS),
                            help="Tipo broker: %s." % ", ".join(sorted(_KINDS)))
        parser.add_argument("--id", type=int, help="PK del broker da cancellare.")
        parser.add_argument("--keep-leads", action="store_true",
                            help="Cancella SOLO il record broker; lascia i lead "
                                 "(diventano orfani, come il pulsante del CRM).")
        parser.add_argument("--yes", action="store_true",
                            help="Esegui davvero. Senza questo flag e' un dry-run.")

    def handle(self, *args, **opts):
        if opts["list"]:
            self._list()
            return

        broker = self._resolve(opts.get("kind"), opts.get("id"))

        leads = Lead.for_broker(broker)
        n_leads = leads.count()
        n_logs = PushLog.objects.filter(lead__in=leads).count()
        keep_leads = opts["keep_leads"]

        self.stdout.write(
            "Broker: %s:%s  «%s»%s"
            % (broker.kind, broker.pk, broker.name,
               "" if broker.is_active else "  (inattivo)"))
        if keep_leads:
            self.stdout.write(
                "  → cancello SOLO il broker; %d lead resteranno (orfani), "
                "%d push log intatti." % (n_leads, n_logs))
        else:
            self.stdout.write(
                "  → cancello broker + %d lead + %d push log." % (n_leads, n_logs))

        if not opts["yes"]:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN: non ho cancellato niente. Ri-lancia con --yes per eseguire."))
            return

        with transaction.atomic():
            if not keep_leads:
                # leads.delete() cascata sui PushLog (FK on_delete=CASCADE).
                deleted_leads, _ = leads.delete()
            else:
                deleted_leads = 0
            name = broker.name
            broker.delete()

        if keep_leads:
            self.stdout.write(self.style.SUCCESS(
                "Fatto: broker «%s» cancellato. %d lead orfani lasciati." % (name, n_leads)))
        else:
            self.stdout.write(self.style.SUCCESS(
                "Fatto: broker «%s» + %d lead + %d push log cancellati."
                % (name, n_leads, n_logs)))

    # ── helper ────────────────────────────────────────────────────────────
    def _list(self):
        any_row = False
        for model in BROKER_MODELS:
            for b in model.objects.all().order_by("pk"):
                any_row = True
                self.stdout.write(
                    "%-10s pk=%-4s lead=%-4s %s %s"
                    % (b.kind, b.pk, Lead.for_broker(b).count(),
                       "attivo " if b.is_active else "inattivo",
                       b.name))
        if not any_row:
            self.stdout.write("Nessun broker configurato.")

    def _resolve(self, kind, pk):
        if pk is None:
            raise CommandError("Manca --id (il pk del broker). Usa --list per vederli.")
        if kind:
            broker = broker_by_kind(kind, pk)
            if broker is None:
                raise CommandError("Nessun broker %s con pk=%s." % (kind, pk))
            return broker
        # Nessun kind: cerco il pk in tutte le tabelle e disambiguo.
        matches = []
        for model in BROKER_MODELS:
            b = model.objects.filter(pk=pk).first()
            if b:
                matches.append(b)
        if not matches:
            raise CommandError(
                "Nessun broker con pk=%s in nessuna tabella. Usa --list." % pk)
        if len(matches) > 1:
            found = ", ".join("%s:%s" % (b.kind, b.pk) for b in matches)
            raise CommandError(
                "pk=%s esiste in piu' tabelle (%s). Specifica --kind." % (pk, found))
        return matches[0]
