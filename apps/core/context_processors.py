from django.conf import settings

from apps.core.navigation import get_nav_groups, get_palette_entries


def navigation(request):
    user = getattr(request, "user", None)
    return {
        "nav_groups": get_nav_groups(user),
        "nav_items_json": get_palette_entries(user),
        "current_path": request.path,
    }


def demo_mode(request):
    """Expose demo credentials to templates when DEMO_MODE is on.

    Used by the login page to pre-fill username/password fields and show
    a small reviewer banner. Off by default — only dev.py opts in.
    """
    if not getattr(settings, "DEMO_MODE", False):
        return {"demo_mode": False}
    return {
        "demo_mode": True,
        "demo_username": getattr(settings, "DEMO_USERNAME", "demo"),
        "demo_password": getattr(settings, "DEMO_PASSWORD", ""),
    }


def page_accent(request):
    """Classe CSS per-pagina (es. 'page-lead') usata dal <body> per dare a
    ogni sezione il suo colore-accento sovrascrivendo --primary in tema chiaro."""
    rm = getattr(request, "resolver_match", None)
    cls = ""
    if rm is not None:
        ns = (rm.namespaces[0] if rm.namespaces else "")
        name = rm.url_name or ""
        view = rm.view_name or ""
        if view == "dashboard_crm":
            cls = "page-crm"
        elif view == "dashboard":
            cls = "page-dashboard"
        elif ns == "tracking":
            if name.startswith("broker"):
                cls = "page-broker-api"
            elif name == "guide":
                cls = "page-guida"
            else:
                cls = "page-lead"
        elif ns == "users":
            cls = "page-users"
        elif ns == "settings":
            cls = "page-settings"
        elif ns == "admin":
            cls = "page-administration"
    return {"page_accent_class": cls}
