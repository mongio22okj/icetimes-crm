"""Playbook automatico: trova i lead fermi da oltre 30 minuti (ancora 'Nuovo',
nessun esito/deposito), diagnostica la causa e crea una notifica nel CRM.

La CORREZIONE resta manuale (caso per caso): qui facciamo solo la DIAGNOSI
read-only e l'avviso. Nessuna chiamata al broker.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.notifications.dispatch import notify
from apps.tracking.models import Lead

STUCK_MINUTES = 30
WINDOW_DAYS = 3  # ignora lead piu' vecchi di cosi' (storia, non vale avvisare)


class Command(BaseCommand):
    help = ("Lead fermi da +%d min senza progressione: diagnostica e notifica "
            "nel CRM." % STUCK_MINUTES)

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff = now - timedelta(minutes=STUCK_MINUTES)
        floor = now - timedelta(days=WINDOW_DAYS)
        stuck = Lead.objects.filter(
            stage="nuovo", is_deposit=False,
            created_at__lt=cutoff, created_at__gte=floor,
        )
        User = get_user_model()
        recipients = list(User.objects.filter(is_active=True).filter(
            Q(is_superuser=True) | Q(role__in=["admin", "manager"])))

        notified = 0
        for lead in stuck:
            payload = dict(lead.payload or {})
            if payload.get("stuck_notified"):
                continue
            cause = self._diagnose(lead)
            who = lead.email or lead.phone or lead.firstname or ("#%s" % lead.id)
            title = "Lead fermo da oltre 30 min"
            body = "%s (%s) — %s" % (who, lead.broker_name or "senza broker", cause)
            url = reverse("tracking:lead_list")
            for u in recipients:
                notify(recipient=u, category="system", title=title, body=body,
                       target_url=url, kind="lead_stuck")
            payload["stuck_notified"] = now.isoformat()
            payload["stuck_cause"] = cause
            lead.payload = payload
            lead.save(update_fields=["payload"])
            notified += 1

        self.stdout.write("Stuck: %d nuovi notificati su %d fermi (a %d destinatari)."
                          % (notified, stuck.count(), len(recipients)))

    def _diagnose(self, lead):
        if not lead.broker_lead_id:
            pl = lead.push_logs.order_by("-created_at").first()
            err = (pl.error if pl and pl.error else "") or "push non accettato"
            return "Push RESPINTO dal broker: %s" % err[:140]
        if lead.last_pull_at is None:
            return ("Mai agganciato dalla pull (id/click_id non combaciano o lead "
                    "assente lato broker)")
        last = timezone.localtime(lead.last_pull_at).strftime("%d/%m %H:%M")
        return ("Status fermo lato broker: agganciato ma nessun esito via API "
                "(ultima pull %s)" % last)
