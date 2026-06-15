"""Realtime fan-out dei nuovi lead.

Un singolo signal `post_save` su Lead copre TUTTI i punti di creazione
(postback broker, /api/track/lead/, landing /b/<slug>/submit/, admin),
così la dashboard dello staff si aggiorna in tempo reale senza refresh.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Lead


@receiver(post_save, sender=Lead, dispatch_uid="leads_new_lead_realtime")
def _broadcast_new_lead(sender, instance: Lead, created: bool, **kwargs):
    if not created:
        return
    try:
        from apps.realtime.dispatch import broadcast_new_lead
        broadcast_new_lead({
            "id": instance.pk,
            "name": instance.full_name or instance.email or f"Lead {instance.pk}",
            "email": instance.email,
            "phone": instance.phone,
            "country": instance.country,
            "source": instance.source,
            "score": instance.score,
        })
    except Exception:  # noqa: BLE001 — il realtime non deve mai bloccare un save
        pass
