"""Multi-step onboarding wizard with session-backed state.

Each step view:
1. On GET: render the form pre-populated from session.
2. On POST: validate, merge into session["wizard"], redirect to next step.

Earlier steps must be filled before later ones (skip-ahead redirects to
the first incomplete step). Final step persists a WizardSubmission and
clears session state.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.wizard.forms import AccountStepForm, CompanyStepForm, PreferencesStepForm
from apps.wizard.models import WizardSubmission

SESSION_KEY = "wizard"


class _WizardMixin(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin):
    breadcrumb_title = "Onboarding"


def _data(request) -> dict:
    return request.session.get(SESSION_KEY, {})


def _save(request, **patch):
    state = _data(request)
    state.update(patch)
    request.session[SESSION_KEY] = state
    request.session.modified = True


class StartView(_WizardMixin, View):
    """GET /wizard/ → reset state and redirect to step 1."""

    def get(self, request):
        request.session.pop(SESSION_KEY, None)
        return redirect("wizard:step1")


class Step1View(_WizardMixin, View):
    template_name = "wizard/step1.html"

    def get(self, request):
        return render(request, self.template_name, {
            "form": AccountStepForm(initial=_data(request)),
            "step": 1,
        })

    def post(self, request):
        form = AccountStepForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "step": 1})
        _save(request, name=form.cleaned_data["name"], email=form.cleaned_data["email"])
        return redirect("wizard:step2")


class Step2View(_WizardMixin, View):
    template_name = "wizard/step2.html"

    def get(self, request):
        if not _data(request).get("name"):
            return redirect("wizard:step1")
        return render(request, self.template_name, {
            "form": CompanyStepForm(initial=_data(request)),
            "step": 2,
        })

    def post(self, request):
        form = CompanyStepForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "step": 2})
        _save(
            request,
            company=form.cleaned_data["company"],
            role=form.cleaned_data["role"],
            team_size=form.cleaned_data["team_size"],
        )
        return redirect("wizard:step3")


class Step3View(_WizardMixin, View):
    template_name = "wizard/step3.html"

    def get(self, request):
        if not _data(request).get("team_size"):
            return redirect("wizard:step2")
        return render(request, self.template_name, {
            "form": PreferencesStepForm(initial=_data(request)),
            "step": 3,
        })

    def post(self, request):
        form = PreferencesStepForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "step": 3})
        _save(
            request,
            theme=form.cleaned_data["theme"],
            notifications_enabled=form.cleaned_data["notifications_enabled"],
        )
        return redirect("wizard:review")


class ReviewView(_WizardMixin, View):
    template_name = "wizard/review.html"

    def get(self, request):
        data = _data(request)
        if not data.get("theme"):
            return redirect("wizard:step3")
        return render(request, self.template_name, {"data": data, "step": 4})

    def post(self, request):
        data = _data(request)
        if not data.get("theme"):
            return redirect("wizard:step1")
        WizardSubmission.objects.create(
            user=request.user,
            name=data.get("name", ""),
            email=data.get("email", ""),
            company=data.get("company", ""),
            role=data.get("role", ""),
            team_size=data.get("team_size", ""),
            theme=data.get("theme", "system"),
            notifications_enabled=bool(data.get("notifications_enabled")),
        )
        request.session.pop(SESSION_KEY, None)
        messages.success(request, "Onboarding submitted.")
        return redirect("wizard:done")


class DoneView(_WizardMixin, View):
    template_name = "wizard/done.html"

    def get(self, request):
        return render(request, self.template_name, {"step": 5})
