"""View mixins for org-aware + RBAC-aware views.

  - `OrgRequiredMixin` — redirects to a "create your first org" page
    if the request has no active organization.
  - `HasRoleMixin` — enforces a minimum role for the current org
    membership (owner > admin > billing > member > viewer per
    `role_at_least`).
  - `OrgScopedMixin` — opt-in helper for list views that have an
    `organization` FK on their model. Filters the queryset to the
    active org. Apply gradually as you migrate models.
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from apps.organizations.models import role_at_least


class OrgRequiredMixin:
    """Bounce out to org creation when no active org is set."""

    no_org_redirect_to = "organizations:list"

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request, "organization", None):
            return redirect(self.no_org_redirect_to)
        return super().dispatch(request, *args, **kwargs)


class HasRoleMixin:
    """Require the current user's membership role be ≥ `required_role`.

    Set `required_role` on the subclass (default 'member'). Anonymous,
    non-member, or insufficient-role requests get a 403.
    """
    required_role: str = "member"

    def dispatch(self, request, *args, **kwargs):
        membership_role = getattr(request, "organization_role", None)
        if membership_role is None:
            raise PermissionDenied("Not a member of an organization.")
        if not role_at_least(membership_role, self.required_role):
            raise PermissionDenied(
                f"This action requires at least the {self.required_role!r} role.",
            )
        return super().dispatch(request, *args, **kwargs)


class OrgScopedMixin:
    """Restrict a ListView's queryset to the request's active organization.

    Subclass requirements:
      - `model` must have an `organization` FK (or override `org_field`)
      - `request.organization` must be set (combine with OrgRequiredMixin)

    This mixin is OPT-IN. Existing list views aren't affected until you
    add it. Phase 16 doesn't migrate every model to add the FK — that
    work happens incrementally per app.
    """
    org_field: str = "organization"

    def get_queryset(self):
        qs = super().get_queryset()
        org = getattr(self.request, "organization", None)
        if org is None:
            return qs.none()
        return qs.filter(**{self.org_field: org})
