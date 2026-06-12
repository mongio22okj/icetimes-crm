"""Single source of truth for sidebar navigation and command-palette entries.

Labels + group names use gettext_lazy so they translate per-request based
on the active locale. The accessor functions force_str() before returning
so callers (templates, JSON serializers, tests) see real strings.
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


# Group labels — defined once so each NavItem can reference the same proxy.
G_DASHBOARDS = _("Dashboards")
G_COMMERCE = _("Commerce")
G_APPS = _("Apps")
G_MARKETING = _("Marketing")
G_SHOWCASE = _("Showcase")
G_ACCOUNT = _("Account")


NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem(_("Leads"), "leads:list", "target",
            keywords=("leads", "crm", "integrations", "deposit"),
            group=G_COMMERCE, requires_staff=True),
    NavItem(_("Customers"), "customers:list", "user-plus",
            keywords=("people", "crm", "customers"), group=G_COMMERCE,
            requires_staff=True),
    NavItem(_("Administration"), "admin:index", "shield",
            keywords=("admin", "administration", "django admin", "models",
                      "permissions", "auth", "groups", "site admin"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem(_("Users"), "users:list", "users",
            keywords=("team", "staff", "members"), group=G_ACCOUNT,
            requires_staff=True),
    NavItem(_("API Broker"), "leads:api_broker", "plug",
            keywords=("api", "broker", "sources", "token", "integration",
                      "send lead", "push"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem(_("API & Integrazioni"), "leads:integrations", "code-2",
            keywords=("api", "integrations", "docs", "rest", "webhook",
                      "embed", "affiliate", "code examples"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem(_("API Manager (semplice)"), "leads:api_manager_simple", "table",
            keywords=("api", "manager", "simple", "test", "table",
                      "client-side"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem(_("Settings"), "settings:profile", "settings",
            keywords=("account", "profile", "preferences"), group=G_ACCOUNT),
)


def get_visible_items(user) -> list[NavItem]:
    if user is None or not getattr(user, "is_authenticated", False):
        return [i for i in NAV_ITEMS if not i.requires_staff]
    return [i for i in NAV_ITEMS if not i.requires_staff or user.is_staff]


def get_nav_groups(user) -> list[dict]:
    """Shape visible items for the sidebar (grouped, ordered).

    Forces lazy proxy strings to str() so template rendering and test
    comparisons see real strings under the active locale.
    """
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
