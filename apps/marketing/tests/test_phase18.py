"""Phase 18 — marketing polish: changelog page, roadmap, compare,
showcase, SEO meta, sitemap, robots.txt.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Changelog parser ──────────────────────────────────────────────────


def test_parse_changelog_returns_releases_in_order():
    from apps.marketing.changelog import parse_changelog
    releases = parse_changelog()
    assert len(releases) >= 4  # at minimum the phases we've shipped
    # Newest release first.
    assert releases[0].date >= releases[-1].date


def test_parse_changelog_extracts_anchor_from_version():
    from apps.marketing.changelog import parse_changelog
    rel = parse_changelog()[0]
    # Anchor is dot→dash, prefixed with "v".
    assert rel.anchor.startswith("v")
    assert "." not in rel.anchor


def test_parse_changelog_renders_inline_code_to_html():
    from apps.marketing.changelog import _inline
    html = _inline("Visit `/components/` for more.")
    assert "<code" in html
    assert "/components/" in html


def test_parse_changelog_renders_bold_to_strong():
    from apps.marketing.changelog import _inline
    html = _inline("**Hello** world")
    assert "<strong" in html
    assert "Hello" in html


def test_parse_changelog_escapes_html_in_input():
    from apps.marketing.changelog import _inline
    html = _inline("<script>alert(1)</script>")
    assert "<script" not in html
    assert "&lt;script&gt;" in html


def test_parse_changelog_extracts_summary():
    from apps.marketing.changelog import parse_changelog
    releases = parse_changelog()
    # Every release should have a non-empty summary (the first paragraph).
    assert all(r.summary for r in releases)


# ── Pages render ──────────────────────────────────────────────────────


@pytest.mark.parametrize("name,marker", [
    ("marketing:changelog", "Changelog"),
    ("marketing:roadmap",   "roadmap"),
    ("marketing:compare",   "Apex vs"),
    ("marketing:showcase",  "Showcase"),
])
def test_marketing_page_renders(client, name, marker):
    r = client.get(reverse(name))
    assert r.status_code == 200
    assert marker.lower() in r.content.decode().lower()


def test_changelog_page_includes_release_anchors(client):
    r = client.get(reverse("marketing:changelog"))
    body = r.content.decode()
    assert 'id="v0-' in body  # at least one anchor like id="v0-13-0"


def test_roadmap_page_has_three_columns(client):
    r = client.get(reverse("marketing:roadmap"))
    body = r.content.decode()
    for label in ("Now", "Next", "Later"):
        assert f">{label}<" in body


def test_compare_page_has_capability_rows(client):
    r = client.get(reverse("marketing:compare"))
    body = r.content.decode()
    assert "REST API" in body
    assert "Roll your own" in body
    assert "Premium templates" in body


def test_showcase_page_links_to_components_and_api(client):
    r = client.get(reverse("marketing:showcase"))
    body = r.content.decode()
    assert "/components/" in body
    assert "/api/v1/docs" in body
    assert "/customers/" in body


# ── SEO meta tags ─────────────────────────────────────────────────────


def test_marketing_page_has_og_meta_tags(client):
    r = client.get(reverse("marketing:hub"))
    body = r.content.decode()
    assert 'property="og:title"' in body
    assert 'property="og:description"' in body
    assert 'property="og:image"' in body
    assert 'rel="canonical"' in body


def test_marketing_page_has_twitter_card(client):
    r = client.get(reverse("marketing:hub"))
    body = r.content.decode()
    assert 'name="twitter:card"' in body


def test_marketing_page_has_jsonld_block(client):
    r = client.get(reverse("marketing:hub"))
    body = r.content.decode()
    assert "application/ld+json" in body
    assert "SoftwareApplication" in body


# ── Sitemap + robots.txt ──────────────────────────────────────────────


def test_sitemap_returns_xml(client):
    r = client.get(reverse("sitemap"))
    assert r.status_code == 200
    assert "application/xml" in r["Content-Type"] or "text/xml" in r["Content-Type"]
    body = r.content.decode()
    assert "<urlset" in body
    # Every Phase 18 page is listed.
    for path in ("changelog", "roadmap", "compare", "showcase"):
        assert f"/landing/{path}/" in body


def test_robots_txt_disallows_admin_and_api(client):
    r = client.get(reverse("robots"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Disallow: /admin/" in body
    assert "Disallow: /api/" in body
    assert "Sitemap:" in body


def test_robots_txt_allows_marketing_and_blog(client):
    r = client.get(reverse("robots"))
    body = r.content.decode()
    assert "Allow: /landing/" in body
    assert "Allow: /blog/" in body
