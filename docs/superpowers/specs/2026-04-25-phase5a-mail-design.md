# Phase 5a — Mail Module

**Date:** 2026-04-25
**Status:** Draft (pending approval)
**Scope:** Internal mail surface — staff users send, receive, reply to, star, and trash messages between each other. Three-pane layout (folder list + message list + thread/compose pane), 5 folders (Inbox, Sent, Drafts, Starred, Trash), Django-native forms with HTMX-driven star/trash toggles. Emits notifications via Phase 4c on new mail arrival.

## Context

Mail is the heaviest "app" surface in the parity roadmap. The reference Apex Next.js dashboard models it as a classic three-pane email client. Phase 4c just shipped Notifications, and 5a leverages it directly: every received message creates a `new_mail` notification. The roadmap's [open questions](../plans/2026-04-24-apex-parity-roadmap.md#decisions-proposed-defaults--revise-if-any-feel-wrong) for 5a resolve as:

- **Threading model:** `parent` self-FK on Message creates the reply chain. To list a "thread", traverse the chain. No separate `Thread` model — keeps the schema lean and reply chains shallow in practice.
- **Rich-text compose:** plain `<textarea>`. No Trix/Quill — adds a JS dep and accessibility concerns; users can type plain text fine for the parity demo.
- **Attachments:** none in 5a. Phase 6c Files will add storage; messages can later gain `attachments = M2M(File)` without schema breakage.
- **Search:** none in 5a. The header palette is the existing global search; mail-specific search is a future enhancement.

## Goals

Ship a credible internal-mail surface that exercises the three-pane layout pattern (which Chat in 5b will reuse), with 5 folders, compose, reply, star/unstar, and soft-trash — without rich text, attachments, multi-recipient, real SMTP, or search.

## Non-goals

- External / SMTP delivery (messages live in DB only)
- Multiple recipients (To/CC/BCC) — single recipient v1
- Forward (only reply)
- Attachments / file uploads (deferred to Phase 6c)
- Rich-text editor (plain textarea + linebreaks rendering)
- Custom labels / folders beyond the fixed 5
- Search within mail
- Email templates / signatures
- "Mark as unread" toggle (one-way: opening marks read; no manual unread)
- Sender state on sent messages (sender can't star/trash their *own* sent copies in 5a — recipient state only)

## Features

| Feature | Behaviour |
|---|---|
| **Compose** | Form with `to` (User dropdown — staff only), `subject`, `body`. "Send" creates a Message with `sent_at=now`; "Save draft" leaves `sent_at=NULL`. New mail triggers `notify_new_mail(recipient, message)`. |
| **Inbox** | Recipient's received messages where `sent_at IS NOT NULL AND NOT is_trashed`. Most-recent first. Unread visually distinguished (bold + dot). |
| **Sent** | Sender's sent messages where `sent_at IS NOT NULL`. |
| **Drafts** | Sender's drafts where `sent_at IS NULL`. Edit → reopens compose with body prefilled. Discard → deletes. |
| **Starred** | Recipient's received messages where `is_starred AND NOT is_trashed`. |
| **Trash** | Recipient's received messages where `is_trashed`. (Restoring is out of scope; permanent delete deferred.) |
| **Thread view** | Selecting a message opens the right pane: subject + sender + body + chain of replies (via `parent` traversal). Reply button opens an inline reply form below the thread. |
| **Star toggle** | POST `/mail/<pk>/star/` flips `is_starred`. HTMX-friendly: returns the updated row partial. |
| **Trash toggle** | POST `/mail/<pk>/trash/` flips `is_trashed`. From inbox view: removes row; from trash view: restores. |
| **Mark read on open** | Opening a message sets `is_read = True` (idempotent). |
| **New-mail notification** | `notify_new_mail` adds `"new_mail"` to `KIND_CHOICES` via migration. Recipient gets a notification linking to `/mail/<message.pk>/`. |

## Architecture

### URLs

```text
apex/urls.py
  /mail/ → include("apps.mail.urls")

apps/mail/urls.py  (app_name = "mail")
  ""                          → InboxView                (name="inbox")        # default redirect to /mail/inbox/
  "inbox/"                    → InboxView                (name="inbox_list")
  "sent/"                     → SentView                 (name="sent")
  "drafts/"                   → DraftsView               (name="drafts")
  "starred/"                  → StarredView              (name="starred")
  "trash/"                    → TrashView                (name="trash")
  "compose/"                  → ComposeView              (name="compose")
  "<int:pk>/"                 → ThreadView               (name="thread")
  "<int:pk>/reply/"           → ReplyView                (name="reply")        # POST
  "<int:pk>/star/"            → StarToggleView           (name="star")         # POST
  "<int:pk>/trash/"           → TrashToggleView          (name="trash_toggle") # POST
  "drafts/<int:pk>/edit/"     → DraftEditView            (name="draft_edit")
  "drafts/<int:pk>/discard/"  → DraftDiscardView         (name="draft_discard")# POST
```

### App layout

```text
apps/mail/
├── __init__.py
├── apps.py                MailConfig
├── models.py              Message + MessageQuerySet
├── forms.py               ComposeForm, ReplyForm
├── views.py               12 CBVs (folders + thread + actions)
├── urls.py                12 routes
├── admin.py               Register Message
├── migrations/
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── factories.py       MessageFactory + DraftFactory
    ├── test_models.py     queryset semantics, threading helpers
    ├── test_forms.py      compose/reply validation
    └── test_views.py      folders, thread, star/trash, compose flow
```

### Notifications integration

A second migration on `apps/notifications/` adds `"new_mail"` to `KIND_CHOICES`. New helper in `apps/notifications/dispatch.py`:

```python
def notify_new_mail(message) -> None:
    """Single-recipient mail notification."""
    from apps.notifications.models import Notification
    Notification.objects.create(
        recipient=message.recipient,
        kind="new_mail",
        title=f"{message.sender.get_full_name() or message.sender.username}: {message.subject}",
        body=message.body[:140],
        url=f"/mail/{message.pk}/",
    )
```

Note: this targets the recipient, not all staff. (Mail is a 1:1 communication.) The existing dispatch helpers fan out to all staff because invoice/order events are staff-relevant; mail is recipient-specific.

### Sidebar

In `apps/core/navigation.py`, add to `NAV_ITEMS` (under "Apps" group):

```python
NavItem("Mail", "mail:inbox", "mail",
        keywords=("inbox", "compose", "messages"), group="Apps",
        requires_staff=True),
```

Add `mail` icon to `apps/core/templatetags/apex.py::ICONS`. New "Apps" group appears between Commerce and Account in the sidebar.

### Three-pane layout

A new `templates/mail/_layout.html` extends `layouts/dashboard.html` and provides:

- Sticky **left sub-pane**: folder links + counts + Compose CTA (~16rem wide)
- **Middle pane**: scrollable message list (~22rem wide)
- **Right pane**: selected thread / compose / empty-state

Folder views (`inbox.html`, `sent.html`, etc.) extend `_layout.html` and fill the middle pane. The right pane content is determined by URL: `/mail/inbox/` → empty placeholder ("Select a message"); `/mail/<pk>/` → thread view; `/mail/compose/` → compose form.

### Views

```python
class _MailMixin(BreadcrumbsMixin, LoginRequiredMixin,
                  EmailVerifiedRequiredMixin, StaffRequiredMixin):
    breadcrumb_title = "Mail"


class InboxView(_MailMixin, ListView):
    model = Message
    paginate_by = 20
    template_name = "mail/inbox.html"
    context_object_name = "messages"

    def get_queryset(self):
        return Message.objects.inbox_for(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["folder"] = "inbox"
        ctx["folder_counts"] = Message.objects.folder_counts(self.request.user)
        return ctx
```

(Sent/Drafts/Starred/Trash follow the same template — they differ only in `get_queryset` and `folder`.)

```python
class ThreadView(_MailMixin, DetailView):
    model = Message
    template_name = "mail/thread.html"
    context_object_name = "message"

    def get_object(self):
        msg = get_object_or_404(
            Message,
            pk=self.kwargs["pk"],
        )
        if self.request.user not in (msg.sender, msg.recipient):
            raise Http404
        # Mark read on open (recipient view only)
        if msg.recipient_id == self.request.user.pk and not msg.is_read:
            msg.is_read = True
            msg.save(update_fields=["is_read"])
        return msg

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["thread"] = self.object.thread_chain()
        ctx["reply_form"] = ReplyForm()
        ctx["folder_counts"] = Message.objects.folder_counts(self.request.user)
        return ctx
```

```python
class ComposeView(_MailMixin, View):
    def get(self, request):
        form = ComposeForm()
        return render(request, "mail/compose.html", {
            "form": form,
            "folder": "compose",
            "folder_counts": Message.objects.folder_counts(request.user),
        })

    def post(self, request):
        form = ComposeForm(request.POST)
        if not form.is_valid():
            return render(request, "mail/compose.html", {
                "form": form,
                "folder": "compose",
                "folder_counts": Message.objects.folder_counts(request.user),
            })
        message = form.save(commit=False)
        message.sender = request.user
        if "save_draft" in request.POST:
            message.sent_at = None
        else:
            message.sent_at = timezone.now()
        message.save()
        if message.sent_at:
            from apps.notifications.dispatch import notify_new_mail
            notify_new_mail(message)
            messages.success(request, "Message sent.")
            return redirect("mail:sent")
        messages.success(request, "Draft saved.")
        return redirect("mail:drafts")
```

`StarToggleView` / `TrashToggleView` are POST-only and HTMX-aware (return refreshed row partial when `HX-Request` is set).

### Data model

```python
# apps/mail/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone


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
        # One query each — pagination already triggers a count, this is fine.
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
        return f"{self.sender}{self.recipient}: {self.subject}"

    def thread_chain(self):
        """Return root → ... → self → replies, in chronological order."""
        # Walk to root
        current = self
        while current.parent_id:
            current = current.parent
        # Collect descendants breadth-first
        chain = [current]
        stack = [current]
        while stack:
            node = stack.pop(0)
            for reply in node.replies.order_by("sent_at", "created_at"):
                chain.append(reply)
                stack.append(reply)
        return chain
```

## Error handling

- **Compose to non-existent user:** ModelChoiceField rejects (form-level error)
- **Compose to self:** allowed (sometimes useful as a self-note); not flagged
- **Reply to a draft:** 404 — drafts aren't reply-able from recipient side because they have no recipient view
- **Cross-user thread access:** `ThreadView.get_object` raises 404 if user is neither sender nor recipient
- **Star/trash toggle on someone else's message:** PK-filtered to (sender=user OR recipient=user) → 404
- **Empty subject/body:** form-level required validation
- **Discarding draft owned by another user:** PK-filtered to sender=user → 404

## Testing

### Unit (~22 new tests)

**`test_models.py` (~8):**
- `inbox_for(user)` excludes drafts, sent items, trashed
- `sent_for(user)` includes only sent (not drafts)
- `drafts_for(user)` includes only drafts (not sent)
- `starred_for(user)` excludes trashed
- `trash_for(user)` includes only trashed received
- `folder_counts(user)` returns correct dict
- `thread_chain()` walks to root + collects replies in order
- `thread_chain()` works for a leaf message (no replies)

**`test_forms.py` (~3):**
- Compose form valid with all fields
- Compose form rejects empty subject
- Reply form valid with body only

**`test_views.py` (~11):**
- Anonymous → /mail/ redirects to login
- Non-staff → 403
- Inbox shows only the user's received non-trashed messages
- Sent shows only the user's outgoing
- Drafts shows only the user's unsent
- Compose POST with subject+body+to creates Message + notification
- Compose with `save_draft` leaves `sent_at=NULL` and emits no notification
- Thread view marks message read on open
- Star toggle flips `is_starred`
- Trash toggle from inbox sets `is_trashed`; from trash unsets
- Reply creates a child message with `parent` set + dispatches notification

### E2E (~4 new tests)

- Inbox: seeded mail visible, click message → opens thread in right pane, marked read
- Compose: open compose, fill in to/subject/body, send → lands on Sent with new message
- Reply: open thread, click Reply, fill body, send → reply visible in thread chain
- Star + Trash: toggle star (persists across nav), trash from inbox → moves to Trash folder

## Rollout — 7 commits

1. **Message model + factory + tests** — schema, queryset, thread walk; pure data layer.
2. **Forms + tests** — `ComposeForm`, `ReplyForm` with widget styling; validation tests.
3. **Views + URLs** — 12 CBVs, full URL namespace, view tests covering all folders + actions.
4. **Three-pane templates** — `_layout.html` shell + folder pages + thread + compose + row partials. Sidebar entry + `mail` icon.
5. **New-mail notification** — second migration adds `"new_mail"` to KIND_CHOICES, `notify_new_mail` dispatch helper, `Compose.post` + `Reply.post` wired to fire it.
6. **seed_demo additions** — generate ~30 messages between demo + batch users, mixed read/starred/trashed states.
7. **E2E tests** — 4 Playwright flows covering inbox click-through, compose, reply, star/trash.

## Open questions

1. **Folder count refresh after star/trash.** When a recipient stars/trashes from inbox, the left sidebar's counts go stale. *Proposed:* HTMX-target the sidebar partial after each action so counts stay in sync. If too noisy, accept the staleness (visible after next navigation).
2. **Empty-state right pane copy.** "Select a message" / "No message selected" / "Inbox zero — well done"? *Proposed:* "Select a message to read."
3. **Thread chain depth limit.** Pathological case: a chain of 1000 replies. *Proposed:* unbounded for v1 (real usage caps under 20); revisit if observed.

## Forward-compatibility notes (5b Chat, 6c Files)

- **Chat (5b):** Reuses the `_layout.html` three-pane shell. Conversation list = left pane, message stream = right pane. Different model (real-time-ish polling) but shared chrome.
- **Files (6c):** Adds `Message.attachments = M2M("files.File")` non-breakingly when ready.
- **Multi-recipient (future):** `Message.recipient` (FK) → `recipients` (M2M) is a one-migration transition. Replace the field, backfill, tests adjust.
- **Search (future):** Postgres `SearchVector` on `(subject, body)`; existing filter chain in `MessageQuerySet` extends naturally.
