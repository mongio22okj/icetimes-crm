from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Lead
from .telegram_notify import notify_new_lead


@receiver(post_save, sender=Lead, dispatch_uid="lead_telegram_notify")
def _notify_lead_created(sender, instance, created, **kwargs):
    if created:
        notify_new_lead(instance)
