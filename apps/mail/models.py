"""Internal mail messages.

One Message per send. Drafts have sent_at IS NULL and only the sender
sees them. Reply threading via self-FK `parent`. State flags
(is_read, is_starred, is_trashed) apply to the recipient view only;
sender state on outgoing messages is deferred (see Phase 5a spec).
"""
from django.conf import settings
from django.db import models


class MessageQuerySet(models.QuerySet):
    def inbox_for(self, user):
        return self.filter(
            recipient=user,
            sent_at__isnull=False,
            is_trashed=False,
        ).select_related("sender")

    def sent_for(self, user):
        return self.filter(
            sender=user,
            sent_at__isnull=False,
        ).select_related("recipient")

    def drafts_for(self, user):
        return self.filter(
            sender=user,
            sent_at__isnull=True,
        ).select_related("recipient")

    def starred_for(self, user):
        return self.filter(
            recipient=user,
            sent_at__isnull=False,
            is_starred=True,
            is_trashed=False,
        ).select_related("sender")

    def trash_for(self, user):
        return self.filter(
            recipient=user,
            sent_at__isnull=False,
            is_trashed=True,
        ).select_related("sender")

    def folder_counts(self, user):
        return {
            "inbox": self.inbox_for(user).count(),
            "inbox_unread": self.inbox_for(user).filter(is_read=False).count(),
            "sent": self.sent_for(user).count(),
            "drafts": self.drafts_for(user).count(),
            "starred": self.starred_for(user).count(),
            "trash": self.trash_for(user).count(),
        }


class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="replies",
    )
    sent_at = models.DateTimeField(null=True, blank=True)  # NULL = draft
    is_read = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    is_trashed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MessageQuerySet.as_manager()

    class Meta:
        ordering = ["-sent_at", "-created_at"]
        indexes = [
            models.Index(fields=["recipient", "sent_at", "is_trashed"]),
            models.Index(fields=["sender", "sent_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.sender_id}->{self.recipient_id}: {self.subject}"

    def thread_chain(self):
        """Return root → ... → all descendants in chronological order."""
        current = self
        while current.parent_id:
            current = current.parent
        chain = [current]
        stack = [current]
        while stack:
            node = stack.pop(0)
            for reply in node.replies.order_by("sent_at", "created_at"):
                chain.append(reply)
                stack.append(reply)
        return chain
