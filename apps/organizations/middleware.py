"""Resolve `request.organization` for every authenticated request.

Order of precedence:
  1. session-stored slug (`organizations.active_slug`) — set by the
     org switcher when the user picks one
  2. user's first Membership (alphabetical by org name) as fallback
  3. None — the user has no memberships yet

Anonymous requests get None. Caller code (views, mixins, templates)
should always check `if request.organization:` before using it.

Side-effect: also sets `request.memberships` as a cached list of the
user's Membership rows so the org switcher can render without extra
queries.
"""
SESSION_KEY = "organizations.active_slug"


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        request.memberships = []
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            try:
                self._attach(request, user)
            except Exception:  # noqa: BLE001 — tenant lookup must not break the request
                pass
        return self.get_response(request)

    def _attach(self, request, user):
        from apps.organizations.models import Membership
        memberships = list(
            Membership.objects.select_related("organization").filter(user=user),
        )
        request.memberships = memberships
        if not memberships:
            return
        # Build a lookup so we can resolve a session-stored slug fast.
        by_slug = {m.organization.slug: m for m in memberships}
        active_slug = request.session.get(SESSION_KEY)
        membership = by_slug.get(active_slug) if active_slug else None
        if membership is None:
            # Pick a stable default: alphabetically-first org by name.
            membership = sorted(
                memberships, key=lambda m: m.organization.name.lower(),
            )[0]
            request.session[SESSION_KEY] = membership.organization.slug
        request.organization = membership.organization
        request.organization_role = membership.role


def set_active_organization(request, organization) -> None:
    """Switch the request session to a different organization.

    Called from the switcher view; rejects orgs the user isn't a
    member of.
    """
    from apps.organizations.models import Membership
    if not request.user.is_authenticated:
        return
    if not Membership.objects.filter(user=request.user, organization=organization).exists():
        return
    request.session[SESSION_KEY] = organization.slug
    request.organization = organization
