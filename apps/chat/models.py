"""1:1 chat messages between staff users.

A "conversation" is implicit: the messages between two users. No
Conversation model — partners are derived via partners_for(user).
"""
from django.conf import settings
from django.db import models


class ChatMessageQuerySet(models.QuerySet):
    def conversation_for(self, user_a, user_b):
        return self.filter(
            models.Q(sender=user_a, recipient=user_b)
            | models.Q(sender=user_b, recipient=user_a)
        ).order_by("sent_at").select_related("sender", "recipient")

    def unread_from(self, sender, recipient):
        return self.filter(sender=sender, recipient=recipient, is_read=False)

    def partners_for(self, user):
        """Return list of dicts: {partner, last_message, unread_count}.

        Sorted by last-message-at descending.
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()
        sent = set(self.filter(sender=user).values_list("recipient", flat=True))
        received = set(self.filter(recipient=user).values_list("sender", flat=True))
        partner_ids = sent | received
        if not partner_ids:
            return []
        partners = User.objects.filter(pk__in=partner_ids)
        rows = []
        for partner in partners:
            convo = self.conversation_for(user, partner)
            last = convo.last()
            unread = self.unread_from(partner, user).count()
            rows.append({
                "partner": partner,
                "last_message": last,
                "unread_count": unread,
            })
        rows.sort(
            key=lambda r: r["last_message"].sent_at if r["last_message"] else None,
            reverse=True,
        )
        return rows


class ChatMessage(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_chat_messages",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_chat_messages",
    )
    body = models.TextField(max_length=2000)
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = ChatMessageQuerySet.as_manager()

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["sender", "recipient", "-sent_at"]),
            models.Index(fields=["recipient", "is_read"]),
        ]

    def __str__(self) -> str:
        return f"{self.sender_id}->{self.recipient_id}: {self.body[:40]}"
