"""Organization management surfaces.

  - `/orgs/` — list of orgs the user belongs to + create new
  - `/orgs/<slug>/settings/` — name / plan / danger zone (owner-only)
  - `/orgs/<slug>/members/` — list, invite, change role, remove
  - `/orgs/switch/<slug>/` — switch the active org for this session
  - `/invitations/<token>/` — accept (or decline) an invitation
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_INFO, LEVEL_SUCCESS, toast
from apps.organizations.middleware import set_active_organization
from apps.organizations.mixins import HasRoleMixin
from apps.organizations.models import (
    PLAN_CHOICES,
    ROLE_ADMIN,
    ROLE_CHOICES,
    ROLE_OWNER,
    Invitation,
    Membership,
    Organization,
)


class _Base(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin):
    pass


# ── Org list + create ─────────────────────────────────────────────────


class OrgListView(_Base, TemplateView):
    template_name = "organizations/list.html"
    breadcrumb_title = "Organizations"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["memberships"] = list(
            Membership.objects.select_related("organization").filter(
                user=self.request.user,
            )
        )
        return ctx

    def post(self, request, *args, **kwargs):
        name = request.POST.get("name", "").strip()
        if not name:
            toast(request, LEVEL_INFO, "Organization name is required.")
            return redirect("organizations:list")
        org = Organization.objects.create(name=name, created_by=request.user)
        Membership.objects.create(user=request.user, organization=org, role=ROLE_OWNER)
        set_active_organization(request, org)
        toast(request, LEVEL_SUCCESS, f"Created '{org.name}'.")
        return redirect("organizations:settings", slug=org.slug)


class OrgSwitchView(_Base, View):
    """Set the session's active organization to <slug>."""
    http_method_names = ["post", "get"]

    def get(self, request, slug):
        return self.post(request, slug)

    def post(self, request, slug):
        org = get_object_or_404(Organization, slug=slug)
        if not Membership.objects.filter(user=request.user, organization=org).exists():
            messages.error(request, "You're not a member of that organization.")
            return redirect("organizations:list")
        set_active_organization(request, org)
        next_url = request.POST.get("next") or request.GET.get("next") or "/"
        return redirect(next_url)


# ── Per-org settings ──────────────────────────────────────────────────


class _OrgScopedBase(_Base):
    """Resolve `self.organization` from the URL slug + verify membership."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.organization = get_object_or_404(Organization, slug=kwargs["slug"])
        try:
            self.membership = Membership.objects.get(
                user=request.user, organization=self.organization,
            )
        except Membership.DoesNotExist:
            messages.error(request, "You're not a member of that organization.")
            return redirect("organizations:list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["organization"] = self.organization
        ctx["membership"] = self.membership
        return ctx


class OrgSettingsView(_OrgScopedBase, HasRoleMixin, TemplateView):
    template_name = "organizations/settings.html"
    breadcrumb_title = "Organization"
    required_role = ROLE_ADMIN

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["plan_choices"] = PLAN_CHOICES
        ctx["member_count"] = self.organization.memberships.count()
        return ctx

    def post(self, request, slug):
        action = request.POST.get("action", "save")
        if action == "delete":
            # Owner-only destructive action.
            if self.membership.role != ROLE_OWNER:
                messages.error(request, "Only the owner can delete the organization.")
                return redirect("organizations:settings", slug=slug)
            name = self.organization.name
            self.organization.delete()
            toast(request, LEVEL_SUCCESS, f"Deleted '{name}'.")
            return redirect("organizations:list")
        # Save name + plan
        name = request.POST.get("name", "").strip() or self.organization.name
        plan = request.POST.get("plan", "").strip() or self.organization.plan
        self.organization.name = name
        # Slug never changes after creation — keeps URLs stable.
        self.organization.plan = plan
        self.organization.save(update_fields=["name", "plan", "updated_at"])
        toast(request, LEVEL_SUCCESS, "Saved.")
        return redirect("organizations:settings", slug=slug)


# ── Members + invitations ─────────────────────────────────────────────


class MembersView(_OrgScopedBase, TemplateView):
    template_name = "organizations/members.html"
    breadcrumb_title = "Members"
    breadcrumb_parent = "organizations:list"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["members"] = list(
            self.organization.memberships.select_related("user").order_by(
                "user__username",
            )
        )
        ctx["pending_invitations"] = list(
            self.organization.invitations.filter(accepted_at__isnull=True)
        )
        ctx["role_choices"] = ROLE_CHOICES
        ctx["can_manage"] = self.membership.role in (ROLE_OWNER, ROLE_ADMIN)
        return ctx


class InviteView(_OrgScopedBase, HasRoleMixin, View):
    required_role = ROLE_ADMIN
    http_method_names = ["post"]

    def post(self, request, slug):
        email = request.POST.get("email", "").strip().lower()
        role = request.POST.get("role", "member")
        if not email:
            toast(request, LEVEL_INFO, "Email required.")
            return redirect("organizations:members", slug=slug)
        if role not in dict(ROLE_CHOICES):
            toast(request, LEVEL_INFO, "Invalid role.")
            return redirect("organizations:members", slug=slug)
        # Don't double-invite an existing pending email.
        if self.organization.invitations.filter(
            email=email, accepted_at__isnull=True,
        ).exists():
            toast(request, LEVEL_INFO, f"Already invited {email}.")
            return redirect("organizations:members", slug=slug)
        invitation = Invitation.create_for(
            self.organization, email=email, role=role, invited_by=request.user,
        )
        # Real apps email the link; for the demo we surface it in the toast
        # so the workflow is testable end-to-end without an email backend.
        link = request.build_absolute_uri(invitation.get_absolute_url())
        toast(request, LEVEL_SUCCESS,
              f"Invited {email}. Share this link: {link}")
        return redirect("organizations:members", slug=slug)


class ChangeRoleView(_OrgScopedBase, HasRoleMixin, View):
    required_role = ROLE_ADMIN
    http_method_names = ["post"]

    def post(self, request, slug, pk):
        target = get_object_or_404(
            Membership, pk=pk, organization=self.organization,
        )
        if target.role == ROLE_OWNER and target.user != request.user:
            messages.error(request, "Can't change the owner's role.")
            return redirect("organizations:members", slug=slug)
        new_role = request.POST.get("role", "")
        if new_role not in dict(ROLE_CHOICES):
            messages.error(request, "Invalid role.")
            return redirect("organizations:members", slug=slug)
        target.role = new_role
        target.save(update_fields=["role"])
        toast(request, LEVEL_SUCCESS, f"Updated {target.user.username} to {new_role}.")
        return redirect("organizations:members", slug=slug)


class RemoveMemberView(_OrgScopedBase, HasRoleMixin, View):
    required_role = ROLE_ADMIN
    http_method_names = ["post"]

    def post(self, request, slug, pk):
        target = get_object_or_404(
            Membership, pk=pk, organization=self.organization,
        )
        if target.role == ROLE_OWNER:
            messages.error(request, "Can't remove the owner — transfer ownership first.")
            return redirect("organizations:members", slug=slug)
        username = target.user.username
        target.delete()
        toast(request, LEVEL_SUCCESS, f"Removed {username} from {self.organization.name}.")
        return redirect("organizations:members", slug=slug)


class CancelInvitationView(_OrgScopedBase, HasRoleMixin, View):
    required_role = ROLE_ADMIN
    http_method_names = ["post"]

    def post(self, request, slug, pk):
        invitation = get_object_or_404(
            Invitation, pk=pk, organization=self.organization,
        )
        invitation.delete()
        toast(request, LEVEL_SUCCESS, "Invitation cancelled.")
        return redirect("organizations:members", slug=slug)


# ── Public invitation accept ──────────────────────────────────────────


class InvitationAcceptView(View):
    """Public — user might not be logged in yet. Renders a confirmation
    page with sign-in CTAs if they need to authenticate first.
    """
    template_name = "organizations/accept_invitation.html"

    def get(self, request, token):
        try:
            invitation = Invitation.objects.select_related("organization").get(token=token)
        except Invitation.DoesNotExist:
            return render(request, self.template_name, {"invalid": True})
        return render(request, self.template_name, {"invitation": invitation})

    def post(self, request, token):
        if not request.user.is_authenticated:
            messages.info(request, "Sign in to accept the invitation.")
            return redirect(f"/accounts/login/?next={request.path}")
        invitation = get_object_or_404(
            Invitation.objects.select_related("organization"), token=token,
        )
        if invitation.is_expired:
            messages.error(request, "This invitation has expired.")
            return render(request, self.template_name, {"invitation": invitation})
        if request.user.email.lower() != invitation.email.lower():
            messages.error(
                request,
                f"This invitation was sent to {invitation.email}; you're signed in as "
                f"{request.user.email}. Sign in with the right account to accept.",
            )
            return render(request, self.template_name, {"invitation": invitation,
                                                        "wrong_user": True})
        invitation.accept(request.user)
        set_active_organization(request, invitation.organization)
        toast(request, LEVEL_SUCCESS,
              f"Joined {invitation.organization.name}.")
        return redirect("/")


