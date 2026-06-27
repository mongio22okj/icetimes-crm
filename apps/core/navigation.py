"""Single source of truth for sidebar navigation and command-palette entries.

Ridotto al CRM lead/broker: mostra solo Dashboard, Lead, Broker API e gli
essenziali Account. Le altre app del template (orders, customers, kanban,
chat, ecc.) restano nel codice ma NON sono esposte nell'interfaccia.
"""
from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class NavItem:
    label: object  # gettext_lazy proxy or str
    url_name: str
    icon: str
    keywords: tuple[str, ...] = ()
    badge: str | None = None
    group: object = "Overview"  # gettext_lazy proxy or str
    requires_staff: bool = False

    def resolved_url(self) -> str:
        return reverse(self.url_name)


# Group labels.
G_CRM = _("CRM")
G_ACCOUNT = _("Account")


NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem(_("CRM"), "dashboard_crm", "trending-up",
            keywords=("crm", "guadagno", "spesa", "profitto", "ftd", "broker",
                      "pipeline", "performance"),
            group=G_CRM, requires_staff=True),
    NavItem(_("Dashboard"), "dashboard", "layout-dashboard",
            keywords=("home", "overview", "dashboard", "kpi", "lead", "ftd"),
            group=G_CRM, requires_staff=True),
    NavItem(_("Lead"), "tracking:lead_list", "target",
            keywords=("lead", "leads", "contatti", "ftd", "tracciamento"),
            group=G_CRM, requires_staff=True),
    NavItem(_("Broker API"), "tracking:broker_list", "plug",
            keywords=("broker", "api", "trackbox", "postback", "landing",
                      "integrazione", "tracciamento"),
            group=G_CRM, requires_staff=True),
    NavItem(_("Administration"), "admin:index", "shield",
            keywords=("admin", "administration", "django admin", "models",
                      "permissions", "auth", "groups", "site admin"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem(_("Users"), "users:list", "users",
            keywords=("team", "staff", "members", "users"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem(_("Settings"), "settings:profile", "settings",
            keywords=("account", "profile", "preferences", "settings"),
            group=G_ACCOUNT),
    NavItem(_("Guida"), "tracking:guide", "book-open",
            keywords=("guida", "help", "aiuto", "manuale", "istruzioni", "guide"),
            group=G_ACCOUNT, requires_staff=True),
)


def get_visible_items(user) -> list[NavItem]:
    if user is None or not getattr(user, "is_authenticated", False):
        return [i for i in NAV_ITEMS if not i.requires_staff]
    return [i for i in NAV_ITEMS if not i.requires_staff or user.is_staff]


def get_nav_groups(user) -> list[dict]:
    """Shape visible items for the sidebar (grouped, ordered)."""
    groups: dict[str, list[dict]] = {}
    for item in get_visible_items(user):
        group_label = str(item.group)
        groups.setdefault(group_label, []).append({
            "label": str(item.label),
            "href": item.resolved_url(),
            "icon": item.icon,
            "badge": item.badge,
        })
    return [{"label": g, "items": items} for g, items in groups.items()]


def get_palette_entries(user) -> list[dict]:
    """Flat serializable list for the command palette's json_script."""
    return [
        {
            "label": str(i.label),
            "url": i.resolved_url(),
            "icon": i.icon,
            "keywords": list(i.keywords),
            "badge": i.badge,
            "group": str(i.group),
        }
        for i in get_visible_items(user)
    ]
