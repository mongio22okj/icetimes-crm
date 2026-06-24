"""Single source of truth for sidebar navigation and command-palette entries."""
from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class NavItem:
    label: str
    url_name: str
    icon: str
    keywords: tuple[str, ...] = ()
    badge: str | None = None
    group: str = "Overview"
    requires_staff: bool = False
    viewer_allowed: bool = False

    def resolved_url(self) -> str:
        return reverse(self.url_name)


G_COMMERCE = "COMMERCE"
G_ACCOUNT = "ACCOUNT"


NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("Dashboard", "dashboard", "layout-dashboard",
            keywords=("dashboard", "home", "overview", "kpi", "stats", "charts"),
            group=G_COMMERCE, requires_staff=True, viewer_allowed=True),
    NavItem("Leads", "leads:list", "target",
            keywords=("leads", "crm", "deposit"),
            group=G_COMMERCE, requires_staff=True, viewer_allowed=True),
    NavItem("Report", "leads:reports", "bar-chart-3",
            keywords=("report", "analytics", "roi", "cpa", "chart", "performance"),
            group=G_COMMERCE, requires_staff=True, viewer_allowed=True),
    NavItem("Broker", "leads:source_list", "building-2",
            keywords=("broker", "api", "lead source", "ping tree", "payout", "fonti"),
            group=G_COMMERCE, requires_staff=True),
    NavItem("Setting API", "leads:api_settings", "plug",
            keywords=("setting api", "api", "broker", "trackbox", "aggiungi broker",
                      "integrazione", "credenziali", "chiavi"),
            group=G_COMMERCE, requires_staff=True),
    NavItem("Campagne", "leads:campaign_list", "megaphone",
            keywords=("campagne", "ads", "facebook", "google", "tiktok", "cpa", "landing"),
            group=G_COMMERCE, requires_staff=True),
    NavItem("TrackBox", "leads:trackbox", "table",
            keywords=("trackbox", "integrazioni", "tipi", "broker", "irev", "affinitrax"),
            group=G_COMMERCE, requires_staff=True),
    NavItem("Link", "leads:tracking_links", "link",
            keywords=("link", "tracking", "tracciamento", "redirect", "click", "url corto"),
            group=G_COMMERCE, requires_staff=True),
    NavItem("Pre-landing", "leads:prelandings", "file-text",
            keywords=("pre-landing", "prelander", "pre lander", "pagina ponte",
                      "advertorial", "ponte", "landing esterna"),
            group=G_COMMERCE, requires_staff=True),
    NavItem("Visualizzatori", "leads:viewer_requests", "user-check",
            keywords=("visualizzatori", "viewer", "accessi", "approva", "sola lettura"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem("Administration", "admin:index", "shield",
            keywords=("admin", "django admin", "models", "permissions"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem("Users", "users:list", "users",
            keywords=("team", "staff", "members"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem("Notifiche", "leads:notification_list", "bell",
            keywords=("slack", "discord", "telegram", "webhook", "notifiche"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem("Auto-email", "leads:auto_message_list", "mail",
            keywords=("email", "auto", "template", "speed-to-lead"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem("Dispatch log", "leads:dispatch_log", "rotate-ccw",
            keywords=("dispatch", "ping tree", "log", "history"),
            group=G_ACCOUNT, requires_staff=True),
    NavItem("Settings", "settings:profile", "settings",
            keywords=("account", "profile", "preferences"),
            group=G_ACCOUNT),
)


def get_visible_items(user) -> list[NavItem]:
    if user is None or not getattr(user, "is_authenticated", False):
        return [i for i in NAV_ITEMS if not i.requires_staff]
    is_viewer = user.groups.filter(name="Viewers").exists() if not user.is_staff else False
    return [
        i for i in NAV_ITEMS
        if not i.requires_staff or user.is_staff or (is_viewer and i.viewer_allowed)
    ]


def get_nav_groups(user) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for item in get_visible_items(user):
        groups.setdefault(item.group, []).append({
            "label": item.label,
            "href": item.resolved_url(),
            "icon": item.icon,
            "badge": item.badge,
        })
    return [{"label": g, "items": items} for g, items in groups.items()]


def get_palette_entries(user) -> list[dict]:
    return [
        {
            "label": i.label,
            "url": i.resolved_url(),
            "icon": i.icon,
            "keywords": list(i.keywords),
            "badge": i.badge,
            "group": i.group,
        }
        for i in get_visible_items(user)
    ]
