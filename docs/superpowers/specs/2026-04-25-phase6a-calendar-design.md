# Phase 6a — Calendar Module

**Date:** 2026-04-25
**Status:** Draft
**Scope:** Personal calendar surface with FullCalendar v6 (vanilla JS, CDN). Month/week/day views, event CRUD via modals, JSON event-source endpoint, color-coded categories. Per-user events; staff-only access.

## Context

Calendar is the first phase to introduce a non-trivial vendored JS dependency. The roadmap [Phase 6 group](../plans/2026-04-24-apex-parity-roadmap.md#phase-6a--calendar) flagged FullCalendar v6 (vanilla build) as the chosen library — no React/Vue wrapper, integrates cleanly with the existing Alpine + HTMX stack. Loaded from CDN to match the existing pattern (HTMX, Alpine, ApexCharts all CDN-served from `base.html`).

Open questions resolved:

- **Event source:** JSON endpoint — FullCalendar requests events lazily for the visible date range, which scales better than rendering all events inline.
- **Recurring events:** No. Adds `python-dateutil` + RRULE handling that doesn't materially help parity with Apex Next.js (which doesn't demo recurring either). One row per occurrence; user can duplicate manually.
- **Timezone:** UTC storage (Django `USE_TZ=True` already enforces this). FullCalendar shows browser-local time. No per-user tz selector.

## Goals

Ship a usable personal calendar — view your own events on month/week/day, create/edit/delete via modal forms, color-coded by category — without recurring events, sharing, invites, or external sync.

## Non-goals

- Shared / team calendars (events are per-user, no visibility to others)
- Recurring events (RRULE)
- Per-user timezones
- Event invitations / RSVPs / attendees
- iCal / Google sync / external calendar feeds
- Reminders / push alerts
- Drag-to-resize or drag-to-reschedule (stretch — defer to a follow-up)
- Custom categories (4 fixed)
- All-day vs timed event distinction inside the same view (kept simple via `all_day` flag)
- Search

## Features

| Feature | Behaviour |
|---|---|
| **FullCalendar UI** | Month view default, with week/day toggle buttons in the header. Events fetched as JSON for the visible range. |
| **Event create** | Click a date cell → opens modal with start/end/title/category. Submit POSTs to `/calendar/events/new/`; on success the calendar reloads events. |
| **Event detail / edit / delete** | Click an existing event → opens modal showing details + edit + delete buttons. |
| **Categories** | Fixed 4: meeting (blue), personal (green), deadline (red), holiday (amber). Each event picks one; FullCalendar renders bg-color. |
| **JSON endpoint** | `GET /calendar/events/?start=<iso>&end=<iso>` returns an array of `{id, title, start, end, allDay, color, extendedProps: {category, description}}` filtered to the requesting user. |

## Architecture

### App naming

`apps.calendar` would shadow Python's stdlib `calendar` module. Use **`apps.events`** instead (model is `Event` anyway). URL prefix stays `/calendar/` for user clarity.

### URLs

```text
apex/urls.py
  /calendar/ → include("apps.events.urls")

apps/events/urls.py  (app_name = "events")
  ""                          → CalendarView         (name="calendar")
  "events/"                   → EventJsonView         (name="event_json")    # GET
  "events/new/"               → EventCreateView       (name="create")        # GET form, POST create
  "events/<int:pk>/"          → EventDetailJsonView   (name="detail_json")   # GET — modal data
  "events/<int:pk>/edit/"     → EventUpdateView       (name="edit")          # GET form, POST update
  "events/<int:pk>/delete/"   → EventDeleteView       (name="delete")        # POST
```

### App layout

```text
apps/events/
├── __init__.py
├── apps.py              EventsConfig
├── models.py            Event
├── forms.py             EventForm
├── views.py             5 CBVs
├── urls.py              5 routes
├── admin.py
├── migrations/
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── factories.py     EventFactory
    ├── test_models.py
    └── test_views.py
```

### Data model

```python
# apps/events/models.py
from django.conf import settings
from django.db import models


class Event(models.Model):
    CATEGORY_CHOICES = [
        ("meeting",  "Meeting"),
        ("personal", "Personal"),
        ("deadline", "Deadline"),
        ("holiday",  "Holiday"),
    ]
    CATEGORY_COLORS = {
        "meeting":  "#3b82f6",  # blue
        "personal": "#10b981",  # emerald
        "deadline": "#ef4444",  # red
        "holiday":  "#f59e0b",  # amber
    }

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    all_day = models.BooleanField(default=False)
    category = models.CharField(
        max_length=16, choices=CATEGORY_CHOICES, default="meeting",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start"]
        indexes = [models.Index(fields=["owner", "start"])]

    def __str__(self):
        return f"{self.title} @ {self.start:%Y-%m-%d}"

    @property
    def color(self) -> str:
        return self.CATEGORY_COLORS[self.category]

    def to_fullcalendar(self) -> dict:
        return {
            "id": self.pk,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "allDay": self.all_day,
            "color": self.color,
            "extendedProps": {
                "category": self.category,
                "description": self.description,
            },
        }
```

### Views

`CalendarView` renders `events/calendar.html` with FullCalendar bootstrap.

`EventJsonView` parses `start` / `end` query params, filters events to `(owner=request.user) & (start <= range_end) & (end >= range_start)`, and returns JSON.

CRUD views are minimal Django CBVs that POST/redirect (no fancy modal HTMX yet — keep it standard form posts; the calendar reloads on redirect). For better UX, the form template uses Alpine to render in a modal overlay; submit re-routes server-side.

### FullCalendar integration

`templates/events/calendar.html`:

```django
{% extends "layouts/dashboard.html" %}
{% block head_extra %}
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/index.global.min.css">
{% endblock %}
{% block content %}
<div id="cal-root"></div>
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/index.global.min.js" defer></script>
<script>
document.addEventListener("DOMContentLoaded", () => {
  const cal = new FullCalendar.Calendar(document.getElementById("cal-root"), {
    initialView: "dayGridMonth",
    headerToolbar: {
      left: "prev,next today",
      center: "title",
      right: "dayGridMonth,timeGridWeek,timeGridDay",
    },
    events: "{% url 'events:event_json' %}",
    selectable: true,
    select: info => {
      window.location.href = `{% url 'events:create' %}?start=${info.startStr}&end=${info.endStr}&allDay=${info.allDay}`;
    },
    eventClick: info => {
      window.location.href = `{% url 'events:edit' 0 %}`.replace("/0/", `/${info.event.id}/`);
    },
  });
  cal.render();
});
</script>
{% endblock %}
```

Form templates (`event_form.html`) are standard Django forms with the same Tailwind classes used elsewhere.

### Sidebar

```python
NavItem("Calendar", "events:calendar", "calendar",
        keywords=("schedule", "events", "calendar"),
        group="Apps", requires_staff=True),
```

Add `calendar` icon SVG.

## Testing

### Unit (~10 new tests)

**`test_models.py`:**
- `to_fullcalendar()` returns expected keys + color
- `color` property returns category color

**`test_views.py`:**
- Calendar redirects anonymous, 403 non-staff, 200 staff
- JSON endpoint returns only owner's events
- JSON endpoint filters by start/end query params
- Create POST creates event for current user
- Edit POST cannot modify someone else's event (404)
- Delete POST removes event

### E2E (~3 new tests)

- Calendar page renders with FullCalendar grid
- Seeded events visible in month view
- Create flow: click day → form opens → submit → event visible

## Rollout — 6 commits

1. Event model + factory + tests
2. Views + URLs + JSON endpoint + view tests
3. Calendar template + form template + FullCalendar integration
4. Sidebar entry + calendar icon
5. seed_demo events for demo user
6. E2E tests

## Open questions

1. **Default view.** Month or week? *Proposed:* month (matches typical calendar landing).
2. **Event color override.** Allow per-event override of category color? *Proposed:* No; category is the only knob.
3. **End-after-start validation.** Reject `end < start` at form level. *Proposed:* yes, in `EventForm.clean`.
