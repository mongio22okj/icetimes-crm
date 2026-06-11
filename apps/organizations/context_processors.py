"""Make `organization` + `memberships` available in every template."""


def active_organization(request):
    return {
        "active_organization": getattr(request, "organization", None),
        "active_memberships": getattr(request, "memberships", []),
        "active_organization_role": getattr(request, "organization_role", None),
    }
