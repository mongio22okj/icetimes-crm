"""TableView mixin — server-side sort / filter / paginate / column visibility.

Subclasses set `table_config = TableConfig(...)` and continue to define
`model` (or override `get_queryset`) as in any ListView. The mixin will:

- Apply filters and sort derived from query params (apps.core.tables.filters).
- Paginate per `config.page_size`.
- Render the full template normally; render `_table.html` only when the
  request looks like an HTMX swap (HX-Request header or `?_partial=table`).
- Expose `visible_columns` to the template, derived from per-user
  `UserPreference` (apps.core.tables.prefs) with sensible defaults.
- Support a `?columns=a,b,c` URL param that updates the user's stored
  preference and redirects, so the column-visibility menu can be a
  plain anchor (no JS state required).

Bulk-action POST handling lands in Phase 11 commit 4 — this file's `post`
remains a `405 Method Not Allowed` until then.
"""
from __future__ import annotations

from django.http import (
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
)
from django.urls import reverse
from django.views.generic import ListView

from apps.core.tables.config import BulkAction, TableConfig
from apps.core.tables.filters import apply_filters, apply_sort
from apps.core.tables.prefs import get_visible_columns, set_visible_columns

PARTIAL_PARAM = "_partial"
PARTIAL_VALUE = "table"


class TableView(ListView):
    table_config: TableConfig | None = None

    def _config(self) -> TableConfig:
        if self.table_config is None:
            raise NotImplementedError(
                f"{type(self).__name__} must set `table_config = TableConfig(...)`."
            )
        return self.table_config

    def get_paginate_by(self, queryset):
        return self._config().page_size

    def get_queryset(self):
        qs = super().get_queryset()
        config = self._config()
        qs = apply_filters(qs, self.request.GET, config)
        qs = apply_sort(qs, self.request.GET, config)
        return qs

    def get_template_names(self):
        if self._is_partial_request():
            return ["core/tables/_table.html"]
        return super().get_template_names()

    def _is_partial_request(self) -> bool:
        if self.request.GET.get(PARTIAL_PARAM) == PARTIAL_VALUE:
            return True
        # HTMX requests carry HX-Request: true (case-insensitive header).
        if self.request.headers.get("HX-Request", "").lower() == "true":
            return True
        return False

    # ---- Column visibility ------------------------------------------------

    def _resolve_visible_columns(self) -> set[str]:
        """Return the set of column keys that should render.

        Resolution order:
        1. `?columns=a,b,c` query param (transient view of the table).
        2. Saved user preference (if any).
        3. Defaults: every column not marked priority>=3 (priority>=3 cols
           are still in the registry but hidden by default — users can
           opt them in via the visibility menu).
        Pinned columns are always included regardless of the above.
        """
        config = self._config()
        all_keys = set(config.column_keys())
        pinned = {c.key for c in config.columns if c.pinned}

        raw = self.request.GET.get("columns", "").strip()
        if raw:
            chosen = {c for c in raw.split(",") if c in all_keys}
            return chosen | pinned

        saved = get_visible_columns(self.request.user, config.key)
        if saved is not None:
            return (saved & all_keys) | pinned

        return {c.key for c in config.columns if c.priority < 3} | pinned

    # ---- Column-visibility round-trip via GET ----------------------------

    def _handle_column_save(self):
        """If `?_save_columns=1&columns=a,b,c` is set, persist + redirect.

        Returns an HttpResponse to short-circuit, or None to continue.
        """
        if self.request.GET.get("_save_columns") != "1":
            return None
        if not self.request.user.is_authenticated:
            return None
        config = self._config()
        all_keys = set(config.column_keys())
        chosen = {c for c in self.request.GET.get("columns", "").split(",") if c in all_keys}
        # Always include pinned columns in storage so they survive a partial save.
        chosen |= {c.key for c in config.columns if c.pinned}
        set_visible_columns(self.request.user, config.key, chosen)
        # Drop the save flag from the URL on redirect — keep filter/sort.
        params = self.request.GET.copy()
        params.pop("_save_columns", None)
        params.pop("columns", None)
        target = self.request.path
        qs = params.urlencode()
        return HttpResponseRedirect(f"{target}?{qs}" if qs else target)

    # ---- Standard CBV plumbing -------------------------------------------

    def get(self, request, *args, **kwargs):
        # Handle SavedView management actions (?_view_action=save|delete|default).
        view_response = self._handle_view_action()
        if view_response is not None:
            return view_response
        # Handle export request (?_export=csv|xlsx|pdf).
        export_response = self._handle_export()
        if export_response is not None:
            return export_response
        # Handle column-visibility save (?_save_columns=1).
        save_redirect = self._handle_column_save()
        if save_redirect is not None:
            return save_redirect
        # Apply user's default view if request has no params at all.
        default_redirect = self._maybe_apply_default_view()
        if default_redirect is not None:
            return default_redirect
        return super().get(request, *args, **kwargs)

    # ---- Exports ---------------------------------------------------------

    def _handle_export(self):
        fmt = self.request.GET.get("_export", "").lower()
        if not fmt:
            return None
        config = self._config()
        if fmt not in config.exports:
            return HttpResponseBadRequest(f"Export format {fmt!r} not enabled.")

        from apps.core.tables.exporters import to_csv, to_pdf, to_xlsx
        # Re-build the queryset honoring filters + sort, but skip pagination.
        qs = self.model._default_manager.all() if self.model else self.get_queryset()
        # Reuse get_queryset() exactly so subclass annotations / select_related
        # apply, then strip its pagination/limit (apply_filters/apply_sort
        # don't add limits, so this is safe).
        qs = self.get_queryset()
        stamp = self.request.GET.get("q") or "export"
        base = f"{config.key}-{stamp[:20]}".strip("-").replace(" ", "_") or config.key
        if fmt == "csv":
            return to_csv(qs, config.columns, filename=f"{base}.csv")
        if fmt == "xlsx":
            return to_xlsx(qs, config.columns, filename=f"{base}.xlsx")
        if fmt == "pdf":
            title = config.caption or config.key.title()
            return to_pdf(qs, config.columns, filename=f"{base}.pdf", title=title)
        return None

    # ---- Saved view actions ---------------------------------------------

    def _maybe_apply_default_view(self):
        """If the request URL is bare (no GET params) and the user has a
        default saved view, redirect to that view's params.
        """
        if not self.request.user.is_authenticated:
            return None
        # Don't redirect HTMX swaps — they explicitly carry params.
        if self._is_partial_request():
            return None
        if any(self.request.GET):
            return None
        from apps.core.models import SavedView
        try:
            view = SavedView.objects.get(
                user=self.request.user,
                table_key=self._config().key,
                is_default=True,
            )
        except SavedView.DoesNotExist:
            return None
        from urllib.parse import urlencode
        qs = urlencode(view.params, doseq=True)
        return HttpResponseRedirect(f"{self.request.path}?{qs}" if qs else self.request.path)

    def _handle_view_action(self):
        """Handle ?_view_action=save|delete|default round-trips.

        - `save`: requires `_view_name=…`; persists current GET params under
          that name. Existing entry with the same name is replaced.
        - `delete`: requires `_view_id=…`; removes that view if owned.
        - `default`: requires `_view_id=…`; sets that view as the user's
          default (clears default flag on others for the same table).
        - `clear_default`: requires no extra params; clears default flag.
        """
        action = self.request.GET.get("_view_action")
        if not action:
            return None
        if not self.request.user.is_authenticated:
            return None

        from apps.core.models import SavedView
        config = self._config()

        if action == "save":
            name = self.request.GET.get("_view_name", "").strip()
            if not name:
                return HttpResponseBadRequest("View name required.")
            # Capture params except our own machinery.
            params = self.request.GET.copy()
            for k in ("_view_action", "_view_name", "_view_id",
                      "_save_columns", "_partial", "page"):
                params.pop(k, None)
            SavedView.objects.update_or_create(
                user=self.request.user,
                table_key=config.key,
                name=name,
                defaults={"params": dict(params.lists())},
            )
            from urllib.parse import urlencode
            qs = urlencode(dict(params.lists()), doseq=True)
            return HttpResponseRedirect(f"{self.request.path}?{qs}" if qs else self.request.path)

        if action == "delete":
            view_id = self.request.GET.get("_view_id")
            SavedView.objects.filter(
                user=self.request.user, table_key=config.key, pk=view_id,
            ).delete()
            return HttpResponseRedirect(self.request.path)

        if action == "default":
            view_id = self.request.GET.get("_view_id")
            try:
                view = SavedView.objects.get(
                    user=self.request.user, table_key=config.key, pk=view_id,
                )
            except SavedView.DoesNotExist:
                return HttpResponseBadRequest("View not found.")
            SavedView.objects.filter(
                user=self.request.user, table_key=config.key,
            ).exclude(pk=view.pk).update(is_default=False)
            view.is_default = True
            view.save(update_fields=["is_default"])
            return HttpResponseRedirect(self.request.path)

        if action == "clear_default":
            SavedView.objects.filter(
                user=self.request.user, table_key=config.key, is_default=True,
            ).update(is_default=False)
            return HttpResponseRedirect(self.request.path)

        return HttpResponseBadRequest(f"Unknown view action: {action!r}")

    # ---- Bulk-action dispatch --------------------------------------------

    def post(self, request, *args, **kwargs):
        """Dispatch a bulk action POST to `handle_bulk_action(action, ids)`.

        Subclasses must override `handle_bulk_action`. Returns 405 if the
        table has no bulk_actions configured, 400 if `action` is missing
        or unknown, 400 if `ids` is empty.
        """
        config = self._config()
        if not config.bulk_actions:
            return HttpResponseNotAllowed(["GET"])

        slug = request.POST.get("action", "").strip()
        action = next((a for a in config.bulk_actions if a.slug == slug), None)
        if action is None:
            return HttpResponseBadRequest(f"Unknown action: {slug!r}")

        ids = [pk for pk in request.POST.getlist("ids") if pk]
        if not ids:
            return HttpResponseBadRequest("No rows selected.")

        return self.handle_bulk_action(action, ids, request)

    def handle_bulk_action(self, action: BulkAction, ids: list[str], request):
        """Subclasses implement this to actually perform the action.

        Must return an HttpResponse. Conventionally a redirect back to
        the list view (with current filters preserved by including
        request.GET in the URL).
        """
        raise NotImplementedError(
            f"{type(self).__name__}.handle_bulk_action must be implemented "
            f"because TableConfig.bulk_actions is non-empty."
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        config = self._config()
        ctx["config"] = config
        ctx["visible_columns"] = self._resolve_visible_columns()
        # User's saved views for this table (for the toolbar switcher).
        if self.request.user.is_authenticated:
            from apps.core.models import SavedView
            ctx["saved_views"] = list(
                SavedView.objects.filter(user=self.request.user, table_key=config.key)
            )
        else:
            ctx["saved_views"] = []
        # `is_partial` lets the wrapping page skip header chrome on HTMX
        # swaps (the swap target is just `#table-<key>`, not the whole page).
        ctx["is_partial"] = self._is_partial_request()
        # Empty-state mode detection (consumed by _empty.html).
        params = self.request.GET
        any_filter = bool(params.get("q") or any(
            params.get(c.key) or params.get(f"{c.key}__from") or params.get(f"{c.key}__to")
            for c in config.columns
        ))
        if not ctx["object_list"]:
            unfiltered_count = self.model._default_manager.all().count() if self.model else 0
            if not any_filter and unfiltered_count == 0:
                ctx["empty_mode"] = "no_data"
            else:
                ctx["empty_mode"] = "no_results"
        else:
            ctx["empty_mode"] = None
        ctx["any_filter_active"] = any_filter
        return ctx


def make_save_columns_url(table_url: str, columns: list[str]) -> str:
    """Helper for the column-visibility menu — builds the redirect URL.

    Kept here so templates can reach it via a `{% url %}` reverse + small
    template filter (added in commit 3 follow-up if needed).
    """
    cols = ",".join(sorted(set(columns)))
    return f"{table_url}?_save_columns=1&columns={cols}"


def reverse_table_url(name: str, *args, **kwargs) -> str:
    """Tiny indirection so test fakes can swap reverse() if needed."""
    return reverse(name, args=args, kwargs=kwargs)
