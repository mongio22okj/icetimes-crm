"""Kanban board + card CRUD + SortableJS-driven move endpoint."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, TemplateView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.kanban.forms import CardForm
from apps.kanban.models import Card


class _KanbanMixin(BreadcrumbsMixin, LoginRequiredMixin,
                    EmailVerifiedRequiredMixin, StaffRequiredMixin):
    breadcrumb_title = "Kanban"


class BoardView(_KanbanMixin, TemplateView):
    template_name = "kanban/board.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        grouped = {s[0]: [] for s in Card.STATUS_CHOICES}
        cards = Card.objects.select_related("assignee").order_by(
            "status", "position", "pk",
        )
        for card in cards:
            grouped[card.status].append(card)
        ctx["columns"] = [
            {"key": s[0], "label": s[1], "cards": grouped[s[0]]}
            for s in Card.STATUS_CHOICES
        ]
        return ctx


class CardCreateView(_KanbanMixin, CreateView):
    model = Card
    form_class = CardForm
    template_name = "kanban/card_form.html"
    success_url = reverse_lazy("kanban:board")

    def get_initial(self):
        initial = super().get_initial()
        status = self.request.GET.get("status")
        if status in dict(Card.STATUS_CHOICES):
            initial["status"] = status
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        # New cards land at the bottom of their column
        max_pos = (
            Card.objects.filter(status=form.cleaned_data["status"])
            .order_by("-position").values_list("position", flat=True).first()
        )
        form.instance.position = (max_pos + 1) if max_pos is not None else 0
        messages.success(self.request, "Card created.")
        return super().form_valid(form)


class CardUpdateView(_KanbanMixin, UpdateView):
    model = Card
    form_class = CardForm
    template_name = "kanban/card_form.html"
    success_url = reverse_lazy("kanban:board")

    def form_valid(self, form):
        messages.success(self.request, "Card updated.")
        return super().form_valid(form)


class CardDetailView(CardUpdateView):
    template_name = "kanban/card_detail.html"


class CardDeleteView(_KanbanMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        card = get_object_or_404(Card, pk=pk)
        card.delete()
        messages.success(request, "Card deleted.")
        return redirect("kanban:board")


class CardMoveView(_KanbanMixin, View):
    """POST endpoint called by SortableJS on drop.

    Body params: to=<status>, position=<int>.
    Shifts siblings in the destination column at >= new_position to make room.
    """

    http_method_names = ["post"]

    def post(self, request, pk):
        card = get_object_or_404(Card, pk=pk)
        new_status = request.POST.get("to")
        try:
            new_position = int(request.POST.get("position", 0))
        except (TypeError, ValueError):
            return HttpResponseBadRequest("invalid position")
        if new_status not in dict(Card.STATUS_CHOICES):
            return HttpResponseBadRequest("invalid status")

        # If moving within the same column, simpler reorder:
        if card.status == new_status:
            siblings = Card.objects.filter(status=new_status).exclude(pk=card.pk).order_by("position", "pk")
            new_order = list(siblings)
            new_order.insert(new_position, card)
            for idx, c in enumerate(new_order):
                Card.objects.filter(pk=c.pk).update(position=idx)
        else:
            # Moving across columns — shift destination siblings >= new_position up by 1
            Card.objects.filter(
                status=new_status, position__gte=new_position,
            ).update(position=F("position") + 1)
            card.status = new_status
            card.position = new_position
            card.save(update_fields=["status", "position", "updated_at"])

        if request.headers.get("HX-Request") == "true":
            return HttpResponse(status=204)
        return redirect("kanban:board")
