# Phase 5b — Chat Module

**Date:** 2026-04-25
**Status:** Draft
**Scope:** 1:1 chat between staff users. Conversation list (left pane) + message stream (right pane). HTMX-polled message stream every 3s. Notifications via Phase 4c on new chat message.

## Context

Mail (Phase 5a) just shipped. Chat reuses the layout pattern (sub-sidebar inside the main app shell) but is materially simpler: no folders, no threading, no drafts. A "conversation" is implicit — the set of messages between two users.

Open questions from the [parity roadmap](../plans/2026-04-24-apex-parity-roadmap.md#decisions-proposed-defaults--revise-if-any-feel-wrong) resolve as:

- **Polling interval:** 3 seconds for the active conversation. `every 3s` HTMX poll on the message stream only when a conversation is open. The bell-style global poll (Phase 4c) handles the new-chat notification at 30s — different cadence, different element.
- **Presence:** No true presence in 5b. Optional `User.last_seen` is a future enhancement; the Apex demo doesn't need an online-dot for parity.
- **Message model:** Separate from Mail's. Mail = formal subject + threading; Chat = stream of short bodies. Reuse would force feature creep on Mail; keep them clean.

## Goals

Ship a credible 1:1 chat surface with conversation list, message stream, send-and-poll-for-new-messages flow, and notification on receive — no real-time infrastructure, no group chat, no presence, no attachments.

## Non-goals

- Group chat / multi-party conversations
- Typing indicator
- Read receipts visible to the sender ("delivered" / "seen")
- File / image attachments
- Emoji reactions
- Message editing / deletion
- Search
- WebSocket / SSE real-time
- True presence (online status dot)
- Voice / video
- E2E encryption

## Features

| Feature | Behaviour |
|---|---|
| **Conversation list** | Left sub-sidebar lists each user demo has exchanged messages with, sorted by last-message-at. Each row: avatar/initial + name + truncated last-message preview + unread count badge. |
| **Message stream** | Right pane shows the full chronological stream between current user and selected partner. Sender's bubbles align right; recipient's align left. HTMX-polls `?after=<latest_pk>` every 3s for new messages. |
| **Send** | POST a body to `/chat/<user_pk>/send/`, creates a `ChatMessage`, redirects (or returns HTMX partial) back. Notification dispatched. |
| **Mark read** | When the recipient opens or polls a conversation, all unread messages from that partner are marked read. |
| **New-chat notification** | New `"new_chat"` kind in `Notification.KIND_CHOICES`. Recipient gets one notification per incoming message — title shows sender + body preview. |
| **Sidebar entry** | "Chat" entry under the existing "Apps" group (next to Mail). Staff-only. |
| **Compose new conversation** | "Start chat" button at top of conversation list opens a user picker. |

## Architecture

### URLs

```text
apex/urls.py
  /chat/ → include("apps.chat.urls")

apps/chat/urls.py  (app_name = "chat")
  ""                          → ChatHomeView         (name="home")        # empty right pane
  "new/"                      → NewConversationView  (name="new")         # GET picker, POST navigates
  "<int:user_pk>/"            → ConversationView     (name="conversation")
  "<int:user_pk>/send/"       → SendMessageView      (name="send")        # POST
  "<int:user_pk>/stream/"     → StreamView           (name="stream")      # GET HTMX
```

### App layout

```text
apps/chat/
├── __init__.py
├── apps.py              ChatConfig
├── models.py            ChatMessage + ChatMessageQuerySet (conversation_for, partners_for)
├── forms.py             SendForm (body only)
├── views.py             5 CBVs
├── urls.py              5 routes
├── admin.py             Register ChatMessage
├── migrations/
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── factories.py     ChatMessageFactory
    ├── test_models.py   queryset semantics
    └── test_views.py    home + conversation + send + stream
```

### Notifications integration

Add `"new_chat"` to `Notification.KIND_CHOICES` via second migration on `apps/notifications/`. New helper:

```python
def notify_new_chat(message) -> None:
    Notification.objects.create(
        recipient=message.recipient,
        kind="new_chat",
        title=f"{message.sender.get_full_name() or message.sender.username}: chat",
        body=message.body[:140],
        url=f"/chat/{message.sender_id}/",
    )
```

### Sidebar

```python
NavItem("Chat", "chat:home", "message-circle",
        keywords=("messages", "dm", "im"), group="Apps",
        requires_staff=True),
```

Add `message-circle` icon.

### Two-pane layout

Mail's `_layout.html` is three panes (folders | list | preview); Chat is two panes (conversation list | stream). Different shell:

`templates/chat/_layout.html`:
- Left sub-sidebar (~18rem): conversation list + "Start chat" button
- Right pane: `{% block stream_pane %}` — empty state by default; conversation.html overrides

### Views

```python
class _ChatMixin(BreadcrumbsMixin, LoginRequiredMixin,
                  EmailVerifiedRequiredMixin, StaffRequiredMixin):
    breadcrumb_title = "Chat"


class ChatHomeView(_ChatMixin, View):
    def get(self, request):
        return render(request, "chat/home.html", {
            "conversations": ChatMessage.objects.partners_for(request.user),
        })


class ConversationView(_ChatMixin, View):
    def get(self, request, user_pk):
        partner = get_object_or_404(User, pk=user_pk, is_staff=True, is_active=True)
        if partner == request.user:
            raise Http404
        # Mark unread received messages as read
        ChatMessage.objects.unread_from(partner, request.user).update(
            is_read=True, read_at=timezone.now(),
        )
        messages = ChatMessage.objects.conversation_for(request.user, partner)
        return render(request, "chat/conversation.html", {
            "partner": partner,
            "messages": messages,
            "conversations": ChatMessage.objects.partners_for(request.user),
        })


class SendMessageView(_ChatMixin, View):
    http_method_names = ["post"]

    def post(self, request, user_pk):
        partner = get_object_or_404(User, pk=user_pk, is_staff=True, is_active=True)
        if partner == request.user:
            raise Http404
        body = (request.POST.get("body") or "").strip()
        if not body:
            return redirect("chat:conversation", user_pk=user_pk)
        msg = ChatMessage.objects.create(
            sender=request.user, recipient=partner, body=body[:2000],
        )
        from apps.notifications.dispatch import notify_new_chat
        notify_new_chat(msg)
        return redirect("chat:conversation", user_pk=user_pk)


class StreamView(_ChatMixin, View):
    """HTMX endpoint: returns the full message stream (or only-after-pk if param given)."""

    def get(self, request, user_pk):
        partner = get_object_or_404(User, pk=user_pk)
        ChatMessage.objects.unread_from(partner, request.user).update(
            is_read=True, read_at=timezone.now(),
        )
        messages = ChatMessage.objects.conversation_for(request.user, partner)
        return render(request, "chat/_message_stream.html", {
            "partner": partner,
            "messages": messages,
        })
```

### Data model

```python
# apps/chat/models.py
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
        """Returns dicts {partner, last_message, unread_count} sorted by recency."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # Find all distinct partners
        sent = self.filter(sender=user).values_list("recipient", flat=True)
        received = self.filter(recipient=user).values_list("sender", flat=True)
        partner_ids = set(sent) | set(received)
        rows = []
        for pid in partner_ids:
            partner = User.objects.get(pk=pid)
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
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_chat_messages",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_chat_messages",
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

    def __str__(self):
        return f"{self.sender_id}->{self.recipient_id}: {self.body[:40]}"
```

## Testing

### Unit (~12 new tests)

**`test_models.py` (~5):**
- `conversation_for(a, b)` returns both directions chronologically
- `unread_from(s, r)` filters correctly
- `partners_for(user)` lists each partner once with correct unread count
- `partners_for(user)` sorts by last-message-at descending
- Empty user returns empty list

**`test_views.py` (~7):**
- Home redirects anonymous
- Home returns 200 for staff with conversations list
- Conversation marks received messages read on open
- Conversation 404 if partner is non-staff
- Send creates message + notification + redirects
- Stream HTMX endpoint returns updated messages partial
- Cross-user can't see someone else's chat (no leakage in conversation queryset since it filters on participants)

### E2E (~3 new tests)

- Chat home → list of conversations visible after seed
- Open conversation → message bubbles render
- Send message → appears in stream after redirect

## Rollout — 6 commits

1. ChatMessage model + factory + tests
2. Views + URLs + view tests
3. Two-pane templates + sidebar entry + message-circle icon
4. New-chat notification kind + dispatch helper
5. seed_demo additions
6. E2E tests

## Open questions

1. **Stream rendering on HTMX poll.** Returning the entire conversation each poll is wasteful but simplest. *Proposed:* full re-render for v1; optimize with `?after=<pk>` only if visible perf issues at the demo scale.
2. **Empty conversation pane copy.** *Proposed:* "Pick a conversation to start chatting."
3. **Self-message.** Allowed or rejected? *Proposed:* Reject (Http404) — not a useful pattern in chat UX.
