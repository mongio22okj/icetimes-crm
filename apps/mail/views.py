"""Mail folder + thread + action views.

Folder views (Inbox/Sent/Drafts/Starred/Trash) share a base mixin and
template, parameterized by `folder` context key + queryset. Star/Trash
toggles are POST-only and HTMX-aware (return refreshed row partial).
"""
from django.contrib import messages as django_messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.mail.forms import ComposeForm, ReplyForm
from apps.mail.models import Message


class _MailMixin(BreadcrumbsMixin, LoginRequiredMixin,
                  EmailVerifiedRequiredMixin, StaffRequiredMixin):
    breadcrumb_title = "Mail"


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


class _FolderView(_MailMixin, ListView):
    paginate_by = 20
    template_name = "mail/folder.html"
    context_object_name = "messages"
    folder = "inbox"  # subclasses override

    def get_queryset(self):
        method = getattr(Message.objects, f"{self.folder}_for")
        return method(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["folder"] = self.folder
        ctx["folder_counts"] = Message.objects.folder_counts(self.request.user)
        return ctx


class InboxView(_FolderView):
    folder = "inbox"


class SentView(_FolderView):
    folder = "sent"


class DraftsView(_FolderView):
    folder = "drafts"


class StarredView(_FolderView):
    folder = "starred"


class TrashView(_FolderView):
    folder = "trash"


class ThreadView(_MailMixin, View):
    def get(self, request, pk):
        msg = get_object_or_404(Message, pk=pk)
        if request.user not in (msg.sender, msg.recipient):
            raise Http404("No such message.")
        # Mark as read on first open (recipient view only)
        if msg.recipient_id == request.user.pk and not msg.is_read:
            msg.is_read = True
            msg.save(update_fields=["is_read"])
        return render(request, "mail/thread.html", {
            "message": msg,
            "thread": msg.thread_chain(),
            "reply_form": ReplyForm(),
            "folder": "inbox" if msg.recipient_id == request.user.pk else "sent",
            "folder_counts": Message.objects.folder_counts(request.user),
            "show_right_pane": True,
        })


class ComposeView(_MailMixin, View):
    """GET = blank form; POST = send or save-draft."""

    def get(self, request, pk: int | None = None):
        instance = None
        if pk is not None:
            instance = get_object_or_404(
                Message, pk=pk, sender=request.user, sent_at__isnull=True,
            )
        form = ComposeForm(instance=instance, current_user=request.user)
        return render(request, "mail/compose.html", {
            "form": form,
            "draft": instance,
            "folder": "compose" if instance is None else "drafts",
            "folder_counts": Message.objects.folder_counts(request.user),
            "show_right_pane": True,
        })

    def post(self, request, pk: int | None = None):
        instance = None
        if pk is not None:
            instance = get_object_or_404(
                Message, pk=pk, sender=request.user, sent_at__isnull=True,
            )
        form = ComposeForm(request.POST, instance=instance, current_user=request.user)
        if not form.is_valid():
            return render(request, "mail/compose.html", {
                "form": form,
                "draft": instance,
                "folder": "compose" if instance is None else "drafts",
                "folder_counts": Message.objects.folder_counts(request.user),
                "show_right_pane": True,
            })
        message = form.save(commit=False)
        message.sender = request.user
        if "save_draft" in request.POST:
            message.sent_at = None
            message.save()
            django_messages.success(request, "Draft saved.")
            return redirect("mail:drafts")
        message.sent_at = timezone.now()
        message.save()
        from apps.notifications.dispatch import notify_new_mail
        notify_new_mail(message)
        django_messages.success(request, "Message sent.")
        return redirect("mail:sent")


class ReplyView(_MailMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        parent = get_object_or_404(Message, pk=pk)
        if request.user not in (parent.sender, parent.recipient):
            raise Http404
        form = ReplyForm(request.POST)
        if not form.is_valid():
            django_messages.error(request, "Reply body required.")
            return redirect("mail:thread", pk=parent.pk)
        # Recipient of the reply is the *other* person on the parent
        target = parent.sender if parent.recipient_id == request.user.pk else parent.recipient
        reply = Message.objects.create(
            sender=request.user,
            recipient=target,
            subject=parent.subject if parent.subject.lower().startswith("re:") else f"Re: {parent.subject}",
            body=form.cleaned_data["body"],
            parent=parent,
            sent_at=timezone.now(),
        )
        from apps.notifications.dispatch import notify_new_mail
        notify_new_mail(reply)
        django_messages.success(request, "Reply sent.")
        return redirect("mail:thread", pk=reply.pk)


class StarToggleView(_MailMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        msg = get_object_or_404(
            Message, pk=pk, recipient=request.user, sent_at__isnull=False,
        )
        msg.is_starred = not msg.is_starred
        msg.save(update_fields=["is_starred"])
        if _is_htmx(request):
            return render(request, "mail/_message_row.html", {"message": msg, "folder": request.GET.get("folder", "inbox")})
        return redirect(request.META.get("HTTP_REFERER") or "mail:inbox")


class TrashToggleView(_MailMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        msg = get_object_or_404(
            Message, pk=pk, recipient=request.user, sent_at__isnull=False,
        )
        msg.is_trashed = not msg.is_trashed
        msg.save(update_fields=["is_trashed"])
        django_messages.success(
            request,
            "Moved to trash." if msg.is_trashed else "Restored from trash.",
        )
        return redirect("mail:inbox" if not msg.is_trashed else "mail:trash")


class DraftDiscardView(_MailMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        draft = get_object_or_404(
            Message, pk=pk, sender=request.user, sent_at__isnull=True,
        )
        draft.delete()
        django_messages.success(request, "Draft discarded.")
        return redirect("mail:drafts")
