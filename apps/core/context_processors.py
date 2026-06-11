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
