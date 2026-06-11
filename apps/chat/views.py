"""Chat views — home, conversation, send, stream, new-conversation picker."""
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.chat.models import ChatMessage
from apps.core.breadcrumbs import BreadcrumbsMixin

User = get_user_model()


class _ChatMixin(BreadcrumbsMixin, LoginRequiredMixin,
                  EmailVerifiedRequiredMixin, StaffRequiredMixin):
    breadcrumb_title = "Chat"


class ChatHomeView(_ChatMixin, View):
    def get(self, request):
        return render(request, "chat/home.html", {
            "conversations": ChatMessage.objects.partners_for(request.user),
            "partner": None,
        })


class NewConversationView(_ChatMixin, View):
    """User picker for starting a new conversation. POST navigates."""

    def get(self, request):
        existing_partner_ids = {
            r["partner"].pk
            for r in ChatMessage.objects.partners_for(request.user)
        }
        candidates = User.objects.filter(
            is_staff=True, is_active=True,
        ).exclude(pk=request.user.pk).order_by("username")
        return render(request, "chat/new.html", {
            "candidates": candidates,
            "existing_partner_ids": existing_partner_ids,
            "conversations": ChatMessage.objects.partners_for(request.user),
            "partner": None,
        })


class ConversationView(_ChatMixin, View):
    def get(self, request, user_pk):
        partner = get_object_or_404(
            User, pk=user_pk, is_staff=True, is_active=True,
        )
        if partner == request.user:
            raise Http404
        # Mark unread received messages from this partner as read
        ChatMessage.objects.unread_from(partner, request.user).update(
            is_read=True, read_at=timezone.now(),
        )
        return render(request, "chat/conversation.html", {
            "partner": partner,
            "messages": ChatMessage.objects.conversation_for(request.user, partner),
            "conversations": ChatMessage.objects.partners_for(request.user),
        })


class SendMessageView(_ChatMixin, View):
    http_method_names = ["post"]

    def post(self, request, user_pk):
        partner = get_object_or_404(
            User, pk=user_pk, is_staff=True, is_active=True,
        )
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
    """HTMX endpoint: returns the message stream partial. Marks unread as read."""

    def get(self, request, user_pk):
        partner = get_object_or_404(User, pk=user_pk)
        if partner == request.user:
            raise Http404
        ChatMessage.objects.unread_from(partner, request.user).update(
            is_read=True, read_at=timezone.now(),
        )
        return render(request, "chat/_message_stream.html", {
            "partner": partner,
            "messages": ChatMessage.objects.conversation_for(request.user, partner),
        })
