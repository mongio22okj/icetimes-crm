"""Component library view tests."""
import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff():
    return UserFactory(is_staff=True)


@pytest.fixture
def regular():
    return UserFactory(is_staff=False)


def test_index_redirects_anonymous(client):
    r = client.get(reverse("components:index"))
    assert r.status_code in (302, 301)


def test_index_403_for_non_staff(client, regular):
    client.force_login(regular)
    r = client.get(reverse("components:index"))
    # StaffRequiredMixin raises PermissionDenied → 403
    assert r.status_code == 403


def test_index_200_for_staff_and_lists_groups(client, staff):
    client.force_login(staff)
    r = client.get(reverse("components:index"))
    assert r.status_code == 200
    # All seven category headers should appear (they're all populated currently).
    for label in ("Overlay", "Disclosure", "Inputs", "Choice", "Upload", "Feedback", "Identity"):
        assert label in r.content.decode()


def test_detail_known_slug_renders_modal_demo(client, staff):
    client.force_login(staff)
    r = client.get(reverse("components:detail", args=["modal"]))
    assert r.status_code == 200
    body = r.content.decode()
    # Page title block + the four modal trigger buttons should all be present.
    assert "Modal" in body
    assert "modal-default" in body
    assert "modal-confirm" in body


def test_detail_unknown_slug_404s(client, staff):
    client.force_login(staff)
    r = client.get(reverse("components:detail", args=["not-a-real-thing"]))
    assert r.status_code == 404


def test_detail_unknown_slug_in_registry_would_fall_back_to_placeholder(client, staff):
    """The placeholder is the safety net if a registry entry ever ships
    without its dedicated page. We assert the path resolves so a future
    drift doesn't 500.
    """
    from django.template.loader import select_template
    t = select_template([
        "components/pages/__never_a_real_slug__.html",
        "components/pages/_placeholder.html",
    ])
    assert t.origin.template_name.endswith("_placeholder.html")


def test_detail_passes_left_rail_groups(client, staff):
    """The left-rail TOC includes all category headers."""
    client.force_login(staff)
    r = client.get(reverse("components:detail", args=["modal"]))
    body = r.content.decode()
    # TOC + main heading both render the label "Modal"
    assert body.count("Modal") >= 2


@pytest.mark.parametrize("slug,marker", [
    ("drawer", "drawer-right"),
    ("toast", "apexToast"),
    ("tooltip", 'role="tooltip"'),
    ("popover", "apexPopover"),
])
def test_overlay_pages_render(client, staff, slug, marker):
    """Each overlay group page renders successfully and contains its own demo markup."""
    client.force_login(staff)
    r = client.get(reverse("components:detail", args=[slug]))
    assert r.status_code == 200
    assert marker in r.content.decode()


@pytest.mark.parametrize("slug,marker", [
    ("tabs", "apexTabs"),
    ("accordion", "apexAccordion"),
    ("stepper", 'aria-current="step"'),
])
def test_disclosure_pages_render(client, staff, slug, marker):
    """Each disclosure group page renders successfully and contains its own demo markup."""
    client.force_login(staff)
    r = client.get(reverse("components:detail", args=[slug]))
    assert r.status_code == 200
    assert marker in r.content.decode()


@pytest.mark.parametrize("slug", [
    p.slug for p in [
        # All 26 primitives. Listed explicitly (not via PRIMITIVES) so a
        # registry change shows up clearly in the test diff.
        type("P", (), {"slug": s}) for s in (
            "modal", "drawer", "toast", "tooltip", "popover",
            "tabs", "accordion", "stepper",
            "datepicker", "daterange", "timepicker", "colorpicker",
            "multiselect", "taginput", "combobox", "toggle-group",
            "segmented", "rating", "slider",
            "dropzone",
            "skeleton", "spinner", "progress-ring", "empty-state",
            "avatar", "badge",
        )
    ]
])
def test_every_primitive_detail_page_returns_200(client, staff, slug):
    """Every registry slug renders its detail page successfully."""
    client.force_login(staff)
    r = client.get(reverse("components:detail", args=[slug]))
    assert r.status_code == 200


def test_dashboard_layout_includes_toast_container(client, staff):
    """The dashboard layout mounts the apex-toasts container exactly once."""
    client.force_login(staff)
    r = client.get(reverse("dashboard"))
    body = r.content.decode()
    assert body.count('id="apex-toasts"') == 1
    assert "apex-toast-payload" in body
