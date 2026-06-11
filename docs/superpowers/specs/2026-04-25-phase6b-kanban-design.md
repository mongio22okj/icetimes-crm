# Phase 6b — Kanban Module

**Date:** 2026-04-25
**Status:** Draft
**Scope:** Single global Kanban board with 4 fixed columns (To Do / In Progress / Review / Done). Cards with title/description/assignee/due date/priority. Drag-and-drop between columns via SortableJS (CDN). All staff users see and manipulate the same board.

## Context

Per the roadmap [Phase 6b](../plans/2026-04-24-apex-parity-roadmap.md#phase-6b--kanban) — exercises the HTMX-driven drag-drop pattern usable elsewhere. SortableJS is a small (~40KB) vanilla JS lib, no React/Vue wrappers, served from CDN.

Decisions:

- **Single global board** vs multiple boards per user: single. Simpler, demo-friendly. Multi-board can extend the model with a `Board` FK later without breaking tests.
- **Position ordering:** integer `position` field, rebalanced on conflict. Fractional indexing is overkill at this scale.
- **Card detail:** dedicated page, not modal. Modals require more JS scaffolding; routing-via-URL is consistent with existing CRUD patterns.

## Goals

Ship a usable single-board Kanban with 4 columns, full card CRUD, drag-to-move-between-columns, and visible assignee/priority/due-date — without multiple boards, custom columns, comments, attachments, or per-board filters.

## Non-goals

- Multiple boards
- Custom column names / colors / WIP limits
- Comments / activity log on cards
- Attachments
- Subtasks / checklists
- Card archiving (separate from delete)
- Search
- Per-user filters / "my cards" view
- Bulk operations

## Features

| Feature | Behaviour |
|---|---|
| **Board view** | 4-column grid (todo / in_progress / review / done). Each column = scrollable list of cards. |
| **Card CRUD** | Click card → detail page with edit/delete. "New card" button at top of each column → create form pre-set to that status. |
| **Drag-and-drop** | SortableJS attaches to every column. On drop, POST `/kanban/cards/<pk>/move/?to=<status>&position=<n>`. Server updates status + reflows position values; redirects (or returns 204 for HTMX). |
| **Within-column reorder** | Same `move` endpoint handles reordering within the same column. |
| **Priority & due date** | Cards visually distinguish priority via colored left border; due dates show inline with overdue styling when past. |

## Architecture

### URLs

```text
apex/urls.py
  /kanban/ → include("apps.kanban.urls")

apps/kanban/urls.py  (app_name = "kanban")
  ""                          → BoardView           (name="board")
  "cards/new/"                → CardCreateView      (name="create")
  "cards/<int:pk>/"           → CardDetailView      (name="detail")
  "cards/<int:pk>/edit/"      → CardUpdateView      (name="edit")
  "cards/<int:pk>/delete/"    → CardDeleteView      (name="delete")    # POST
  "cards/<int:pk>/move/"      → CardMoveView        (name="move")      # POST
```

### App layout

```text
apps/kanban/
├── __init__.py
├── apps.py              KanbanConfig
├── models.py            Card + CardQuerySet (by_column)
├── forms.py             CardForm
├── views.py             6 CBVs
├── urls.py              6 routes
├── admin.py
├── migrations/
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── factories.py     CardFactory
    ├── test_models.py
    └── test_views.py
```

### Data model

```python
class Card(models.Model):
    STATUS_CHOICES = [
        ("todo",        "To Do"),
        ("in_progress", "In Progress"),
        ("review",      "Review"),
        ("done",        "Done"),
    ]
    PRIORITY_CHOICES = [
        ("low",  "Low"),
        ("med",  "Medium"),
        ("high", "High"),
    ]
    PRIORITY_BORDER = {
        "low":  "border-l-zinc-400",
        "med":  "border-l-blue-500",
        "high": "border-l-red-500",
    }

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="todo")
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="med")
    position = models.IntegerField(default=0)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="kanban_cards",
    )
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="created_kanban_cards",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "position", "pk"]
        indexes = [models.Index(fields=["status", "position"])]

    @property
    def is_overdue(self) -> bool:
        if not self.due_date or self.status == "done":
            return False
        from django.utils import timezone
        return self.due_date < timezone.now().date()

    @property
    def priority_border_class(self) -> str:
        return self.PRIORITY_BORDER[self.priority]
```

### Board view + drag/drop

`BoardView` groups cards by status:

```python
def get_context_data(self, **kwargs):
    grouped = {s[0]: [] for s in Card.STATUS_CHOICES}
    for card in Card.objects.select_related("assignee").order_by("status", "position", "pk"):
        grouped[card.status].append(card)
    return {**super().get_context_data(**kwargs), "columns": grouped, ...}
```

`CardMoveView`:

```python
def post(self, request, pk):
    card = get_object_or_404(Card, pk=pk)
    new_status = request.POST.get("to")
    new_position = int(request.POST.get("position", 0))
    if new_status not in dict(Card.STATUS_CHOICES):
        return HttpResponseBadRequest()
    # Shift others in target column at >= new_position
    Card.objects.filter(status=new_status, position__gte=new_position).update(
        position=F("position") + 1,
    )
    card.status = new_status
    card.position = new_position
    card.save(update_fields=["status", "position", "updated_at"])
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(status=204)
    return redirect("kanban:board")
```

Position handling is naive (gap-creation via shift). Acceptable at demo scale.

### SortableJS integration

```html
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js"></script>
<script>
document.querySelectorAll("[data-kanban-column]").forEach((col) => {
  Sortable.create(col, {
    group: "kanban",
    animation: 150,
    onEnd: (evt) => {
      const cardId = evt.item.dataset.cardId;
      const targetCol = evt.to.dataset.kanbanColumn;
      const newPosition = evt.newIndex;
      fetch(`/kanban/cards/${cardId}/move/`, {
        method: "POST",
        headers: { "X-CSRFToken": "{{ csrf_token }}", "HX-Request": "true" },
        body: new URLSearchParams({ to: targetCol, position: newPosition }),
      });
    },
  });
});
</script>
```

### Sidebar

```python
NavItem("Kanban", "kanban:board", "trello",
        keywords=("board", "tasks", "kanban"), group="Apps",
        requires_staff=True),
```

Add `trello` icon (or simpler "kanban" SVG).

## Testing

### Unit (~10 new tests)

**`test_models.py`:**
- `is_overdue` true when sent + due past + status != done
- `is_overdue` false when status == done (even if past due)
- `priority_border_class` returns expected class
- Default ordering: by status then position

**`test_views.py`:**
- Board redirects anonymous, 403 non-staff, 200 staff
- Board groups cards by status into `columns` context
- Create POST creates card with assignee
- Move POST updates status and position; shifts others
- Move POST rejects invalid status
- Delete POST removes card

### E2E (~3 new tests)

- Board page renders 4 columns
- Seeded cards visible in correct columns
- Create card flow → card visible after redirect

## Rollout — 6 commits

1. Card model + factory + tests
2. Views + URLs + tests
3. Board template + SortableJS + form template
4. Sidebar entry + icon
5. seed_demo cards
6. E2E tests

## Open questions

1. **Drag-drop without DB position** — should the move endpoint also re-write all sibling positions to keep them dense? *Proposed:* skip dense rewrite for v1; the simple shift is fine.
2. **Card detail page or edit form unified.** *Proposed:* unified — `CardDetailView` IS the edit form, with delete on the side.
