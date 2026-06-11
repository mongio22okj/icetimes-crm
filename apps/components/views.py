"""Component library — index page + per-primitive detail page."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.template import TemplateDoesNotExist
from django.template.loader import select_template
from django.views.generic import TemplateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.components.registry import get_primitive, grouped
from apps.core.breadcrumbs import BreadcrumbsMixin


class _BaseMixin(BreadcrumbsMixin, LoginRequiredMixin,
                 EmailVerifiedRequiredMixin, StaffRequiredMixin):
    pass


class ComponentIndexView(_BaseMixin, TemplateView):
    template_name = "components/index.html"
    breadcrumb_title = "Components"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["groups"] = grouped()
        return ctx


class ComponentDetailView(_BaseMixin, TemplateView):
    breadcrumb_parent = "components:index"

    def get_breadcrumb_title(self) -> str:
        primitive = get_primitive(self.kwargs["slug"])
        return primitive.label if primitive else "Component"

    def get_template_names(self):
        slug = self.kwargs["slug"]
        primitive = get_primitive(slug)
        if primitive is None:
            raise Http404(f"Unknown component: {slug}")
        # Prefer a primitive-specific page; fall back to a placeholder so
        # the index never points at a 500. The placeholder still 200s and
        # tells the user the demo is coming.
        candidates = [
            f"components/pages/{slug}.html",
            "components/pages/_placeholder.html",
        ]
        try:
            return [select_template(candidates).origin.template_name]
        except TemplateDoesNotExist:
            raise Http404(f"No template for component: {slug}") from None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["primitive"] = get_primitive(self.kwargs["slug"])
        ctx["groups"] = grouped()  # left-rail TOC
        return ctx
