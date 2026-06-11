"""Calendar views — main page (FullCalendar UI), JSON event source, CRUD."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.generic import CreateView, TemplateView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.events.forms import EventForm
from apps.events.models import Event


class _EventMixin(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin):
    breadcrumb_title = "Calendar"


class CalendarView(_EventMixin, TemplateView):
    template_name = "events/calendar.html"


class EventJsonView(_EventMixin, View):
    """Returns the user's events that overlap the requested date range.

    Query params: start, end (ISO datetimes from FullCalendar).
    """

    def get(self, request):
        qs = Event.objects.filter(owner=request.user)
        start = parse_datetime(request.GET.get("start") or "") if request.GET.get("start") else None
        end = parse_datetime(request.GET.get("end") or "") if request.GET.get("end") else None
        if start:
            qs = qs.filter(end__gte=start)
        if end:
            qs = qs.filter(start__lte=end)
        return JsonResponse([e.to_fullcalendar() for e in qs], safe=False)


class EventCreateView(_EventMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = "events/event_form.html"
    success_url = reverse_lazy("events:calendar")

    def get_initial(self):
        initial = super().get_initial()
        # Pre-fill from FullCalendar's select range (passed as query params)
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")
        all_day = self.request.GET.get("allDay") == "true"
        if start:
            initial["start"] = parse_datetime(start) or start
        if end:
            initial["end"] = parse_datetime(end) or end
        if all_day:
            initial["all_day"] = True
        return initial

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Event created.")
        return super().form_valid(form)


class EventUpdateView(_EventMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = "events/event_form.html"
    success_url = reverse_lazy("events:calendar")

    def get_queryset(self):
        return Event.objects.filter(owner=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Event updated.")
        return super().form_valid(form)


class EventDeleteView(_EventMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk, owner=request.user)
        event.delete()
        messages.success(request, "Event deleted.")
        return redirect("events:calendar")
