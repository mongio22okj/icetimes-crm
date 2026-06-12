from typing import Any

from django.urls import reverse


class BreadcrumbsMixin:
    """Class-based view mixin that injects a `breadcrumbs` context variable.

    Each view declares:
      - breadcrumb_title: str           (override get_breadcrumb_title for dynamic)
      - breadcrumb_parent: str | tuple[str, str] | None
          URL name of the parent view, or (title, url_name) when the parent
          label should differ from the NAV_ITEMS label (rare).

    The result is a list of (title, href_or_None) tuples; href is None for
    the current (last) crumb.
    """

    breadcrumb_title: str | None = None
    breadcrumb_parent: str | tuple[str, str] | None = None

    def get_breadcrumb_title(self) -> str:
        return self.breadcrumb_title or ""

    def get_breadcrumbs(self) -> list[tuple[str, str | None]]:
        crumbs: list[tuple[str, str | None]] = [("Home", reverse("leads:list"))]
        parent = self.breadcrumb_parent
        if parent:
            if isinstance(parent, tuple):
                title, url_name = parent
            else:
                title, url_name = self._resolve_parent_title(parent), parent
            crumbs.append((title, reverse(url_name)))
        crumbs.append((self.get_breadcrumb_title(), None))
        return crumbs

    @staticmethod
    def _resolve_parent_title(url_name: str) -> str:
        from apps.core.navigation import NAV_ITEMS
        for item in NAV_ITEMS:
            if item.url_name == url_name:
                return item.label
        return url_name.split(":")[-1].replace("_", " ").title()

    def get_context_data(self, **kwargs: Any) -> dict:
        ctx = super().get_context_data(**kwargs) if hasattr(super(), "get_context_data") else {}
        ctx["breadcrumbs"] = self.get_breadcrumbs()
        return ctx
