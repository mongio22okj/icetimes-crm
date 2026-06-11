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
    NavItem(_("Overview"), "dashboard", "layout-dashboard",
            keywords=("home", "overview"), group=G_DASHBOARDS),
    NavItem(_("Analytics"), "dashboard_analytics", "bar-chart-3",
            keywords=("traffic", "visitors", "page views", "analytics"),
            group=G_DASHBOARDS),
    NavItem(_("CRM"), "dashboard_crm", "trending-up",
            keywords=("pipeline", "deals", "sales", "crm"),
            group=G_DASHBOARDS, requires_staff=True),
    NavItem(_("eCommerce"), "dashboard_ecommerce", "shopping-bag",
            keywords=("sales", "products", "orders", "ecommerce"),
            group=G_DASHBOARDS, requires_staff=True),
    NavItem(_("SaaS"), "dashboard_saas", "rocket",
            keywords=("mrr", "subscribers", "churn", "saas"),
            group=G_DASHBOARDS, requires_staff=True),
    NavItem(_("Orders"), "orders:list", "shopping-cart",
            keywords=("sales", "purchases"), group=G_COMMERCE),
    NavItem(_("Customers"), "customers:list", "user-plus",
            keywords=("people", "crm", "customers"), group=G_COMMERCE,
            requires_staff=True),
    NavItem(_("Leads"), "leads:list", "target",
            keywords=("leads", "crm", "integrations", "deposit"),
            group=G_COMMERCE, requires_staff=True),
    NavItem(_("Invoices"), "invoices:list", "file-text",
            keywords=("billing", "finance", "invoices"), group=G_COMMERCE,
            requires_staff=True),
    NavItem(_("Mail"), "mail:inbox", "mail",
            keywords=("inbox", "compose", "messages"), group=G_APPS,
            requires_staff=True),
    NavItem(_("Chat"), "chat:home", "message-circle",
            keywords=("messages", "dm", "im", "chat"), group=G_APPS,
            requires_staff=True),
    NavItem(_("Calendar"), "events:calendar", "calendar",
            keywords=("schedule", "events", "calendar"), group=G_APPS,
            requires_staff=True),
    NavItem(_("Kanban"), "kanban:board", "trello",
            keywords=("board", "tasks", "kanban"), group=G_APPS,
            requires_staff=True),
    NavItem(_("Projects"), "projects:list", "briefcase",
            keywords=("projects", "tasks", "milestones", "team"),
            group=G_APPS, requires_staff=True),
    NavItem(_("Team"), "profiles:list", "user",
            keywords=("people", "team", "directory", "profiles"),
            group=G_APPS),
    NavItem(_("Activity"), "activity:list", "activity",
            keywords=("activity", "audit", "log", "timeline"),
            group=G_APPS, requires_staff=True),
    NavItem(_("Files"), "files:root", "folder",
            keywords=("files", "uploads", "documents"), group=G_APPS,
            requires_staff=True),
    NavItem(_("Realtime"), "realtime:demo", "activity",
            keywords=("realtime", "websocket", "presence", "live",
                      "channels", "notifications"),
            group=G_APPS),
    NavItem(_("Landings"), "marketing:hub", "rocket",
            keywords=("marketing", "landing"), group=G_MARKETING,
            requires_staff=True),
    NavItem(_("Pricing"), "marketing:pricing", "dollar-sign",
            keywords=("pricing", "tiers", "plans"), group=G_MARKETING,
            requires_staff=True),
    NavItem(_("Support"), "marketing:support", "bell",
            keywords=("support", "help", "contact"), group=G_MARKETING,
            requires_staff=True),
    NavItem(_("Help center"), "help_center:home", "book-open",
            keywords=("help", "knowledge base", "articles", "faq", "docs"),
            group=G_MARKETING),
    NavItem(_("Blog"), "blog:list", "file-text",
            keywords=("blog", "posts", "articles", "news"),
            group=G_MARKETING),
    NavItem(_("Onboarding"), "wizard:start", "rocket",
            keywords=("wizard", "onboarding", "guided"), group=G_SHOWCASE,
            requires_staff=True),
    NavItem(_("Components"), "components:index", "blocks",
            keywords=("components", "primitives", "ui", "library", "modal",
                      "drawer", "toast", "tabs", "accordion"),
            group=G_SHOWCASE, requires_staff=True),
    NavItem(_("Charts"), "charts_showcase", "activity",
            keywords=("charts", "graphs", "showcase"), group=G_SHOWCASE,
            requires_staff=True),
    NavItem(_("Coming Soon"), "pages:coming_soon", "rocket",
            keywords=("launch", "countdown", "coming soon"),
            group=G_SHOWCASE, requires_staff=True),
    NavItem(_("Maintenance"), "pages:maintenance", "settings",
            keywords=("maintenance", "downtime", "scheduled"),
            group=G_SHOWCASE, requires_staff=True),
    NavItem(_("503 Page"), "pages:service_unavailable", "activity",
            keywords=("503", "service unavailable", "outage"),
            group=G_SHOWCASE, requires_staff=True),
    NavItem(_("Forms"), "pages:forms_gallery", "file-text",
            keywords=("forms", "inputs", "validation", "wizard"),
            group=G_SHOWCASE, requires_staff=True),
    NavItem(_("Widgets"), "pages:widgets_gallery", "package",
            keywords=("widgets", "components", "cards", "stats"),
            group=G_SHOWCASE, requires_staff=True),
    NavItem(_("Datatable"), "pages:datatable", "trello",
            keywords=("table", "datatable", "sort", "filter", "export"),
            group=G_SHOWCASE, requires_staff=True),
    NavItem(_("API docs"), "pages:api_docs", "book-open",
            keywords=("api", "docs", "endpoints", "developers", "reference"),
            group=G_SHOWCASE, requires_staff=True),
    NavItem(_("Maps"), "pages:maps", "map-pin",
            keywords=("map", "geo", "location", "leaflet"),
            group=G_SHOWCASE, requires_staff=True),
    NavItem(_("Products"), "products:list", "package",
            keywords=("inventory", "catalog"), group=G_COMMERCE),
    NavItem(_("Administration"), "admin:index", "shield",
            keywords=("admin", "administration", "django admin", "models",
                      "permissions", "auth", "groups", "site admin"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem(_("Users"), "users:list", "users",
            keywords=("team", "staff", "members"), group=G_ACCOUNT,
            requires_staff=True),
    NavItem(_("Settings"), "settings:profile", "settings",
            keywords=("account", "profile", "preferences"), group=G_ACCOUNT),
    NavItem(_("Billing"), "billing:overview", "dollar-sign",
            keywords=("subscription", "plan", "payment", "billing", "invoices"),
            group=G_ACCOUNT),
    NavItem(_("Organizations"), "organizations:list", "users",
            keywords=("organization", "workspace", "team", "members",
                      "tenant", "rbac"),
            group=G_ACCOUNT),
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
