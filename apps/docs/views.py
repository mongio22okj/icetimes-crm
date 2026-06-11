"""Public docs surface — no auth required, mirrors the Next.js Apex docs.

Each page is a thin TemplateView. The shared layout lives in
`templates/layouts/docs.html`; each page extends it and supplies a
`page_title` block + body. Nav state and the rest of the chrome
(top bar, sidebar, dark-mode toggle) come from the layout.
"""
from django.views.generic import TemplateView

from apps.docs.nav import DOCS_NAV


class DocsBase(TemplateView):
    """Shared base — every doc page extends this so we can inject context once."""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["docs_nav"] = DOCS_NAV
        # The sidebar template reads `current_doc_url_name` to highlight
        # the active link. resolver_match is populated by Django routing.
        match = self.request.resolver_match
        ctx["current_doc_url_name"] = (
            f"{match.namespace}:{match.url_name}" if match else ""
        )
        return ctx


class IntroductionView(DocsBase):
    template_name = "docs/index.html"


class InstallationView(DocsBase):
    template_name = "docs/installation.html"


class FolderStructureView(DocsBase):
    template_name = "docs/folder_structure.html"


class ArchitectureView(DocsBase):
    template_name = "docs/architecture.html"


class CustomizeView(DocsBase):
    template_name = "docs/customize.html"


class ThemingView(DocsBase):
    template_name = "docs/theming.html"


class AddingPagesView(DocsBase):
    template_name = "docs/adding_pages.html"


class ComponentsView(DocsBase):
    template_name = "docs/components.html"


class ChartsView(DocsBase):
    template_name = "docs/charts.html"


class I18nView(DocsBase):
    template_name = "docs/i18n.html"


class DeploymentView(DocsBase):
    template_name = "docs/deployment.html"


class DemoModeView(DocsBase):
    template_name = "docs/demo_mode.html"


class BackupsView(DocsBase):
    template_name = "docs/backups.html"


class MonitoringView(DocsBase):
    template_name = "docs/monitoring.html"


class RealtimeView(DocsBase):
    template_name = "docs/realtime.html"


class ApiView(DocsBase):
    template_name = "docs/api.html"


class OrganizationsView(DocsBase):
    template_name = "docs/organizations.html"


class TestingView(DocsBase):
    template_name = "docs/testing.html"


class ChangelogView(DocsBase):
    template_name = "docs/changelog.html"


class FaqView(DocsBase):
    template_name = "docs/faq.html"
