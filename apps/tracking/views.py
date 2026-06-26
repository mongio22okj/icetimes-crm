from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin

from .forms import TrackboxBrokerForm
from .models import TrackboxBroker


class TrackboxBrokerListView(BreadcrumbsMixin, LoginRequiredMixin,
                             EmailVerifiedRequiredMixin, StaffRequiredMixin,
                             ListView):
    model = TrackboxBroker
    template_name = "tracking/broker_list.html"
    context_object_name = "brokers"
    breadcrumb_title = "Broker API"


class TrackboxBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, StaffRequiredMixin,
                               CreateView):
    model = TrackboxBroker
    form_class = TrackboxBrokerForm
    template_name = "tracking/broker_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker TrackBox"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return response


class TrackboxBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, StaffRequiredMixin,
                               UpdateView):
    model = TrackboxBroker
    form_class = TrackboxBrokerForm
    template_name = "tracking/broker_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return response


class TrackboxBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               StaffRequiredMixin, View):
    def post(self, request, pk):
        broker = get_object_or_404(TrackboxBroker, pk=pk)
        name = broker.name
        broker.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")
