"""Capture key product screenshots for README + marketing.

Run with the dev server up at http://localhost:8000:
    uv run python scripts/capture_screenshots.py

Saves PNGs into screenshots/.
"""
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)

BASE = os.environ.get("BASE_URL", "http://localhost:8000")
VIEWPORT = {"width": 1440, "height": 900}

# Demo credentials — kept here so the capture script is self-contained.
# Update both this and apex/settings/base.py if rotating.
DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "demo")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "ApexShowcase!2026")

# Pages: (filename, url-path, requires-login, theme)
PAGES = [
    # ── Marketing (no login) ──────────────────────────────────────────
    ("landing-hub.png",          "/landing/",                       False, "light"),
    ("landing-analytics.png",    "/landing/analytics/",             False, "light"),
    ("landing-pricing.png",      "/landing/pricing/",               False, "light"),
    ("login.png",                "/accounts/login/",                False, "light"),

    # ── Status pages (no login) ───────────────────────────────────────
    ("pages-coming-soon.png",    "/pages/coming-soon/",             False, "light"),
    ("pages-maintenance.png",    "/pages/maintenance/",             False, "light"),
    ("pages-503.png",            "/pages/503/",                     False, "light"),

    # ── Public blog (no login) ────────────────────────────────────────
    ("blog-list.png",            "/blog/",                          False, "light"),
    ("blog-detail.png",          "_first_post",                     False, "light"),

    # ── Help center (login required for layout) ───────────────────────
    ("help-home.png",            "/help/",                          True,  "light"),
    ("help-article.png",         "_first_help_article",             True,  "light"),

    # ── Authenticated dashboard surfaces ──────────────────────────────
    ("dashboard.png",            "/",                               True,  "light"),
    ("dashboard-dark.png",       "/",                               True,  "dark"),
    ("dashboard-analytics.png",  "/dashboards/analytics/",          True,  "light"),
    ("dashboard-crm.png",        "/dashboards/crm/",                True,  "light"),
    ("dashboard-ecommerce.png",  "/dashboards/ecommerce/",          True,  "light"),
    ("dashboard-saas.png",       "/dashboards/saas/",               True,  "light"),
    ("dashboard-saas-dark.png",  "/dashboards/saas/",               True,  "dark"),

    # ── Commerce ──────────────────────────────────────────────────────
    ("invoices-list.png",        "/invoices/",                      True,  "light"),
    ("invoice-detail.png",       "_first_invoice",                  True,  "light"),
    ("customers-list.png",       "/customers/",                     True,  "light"),

    # ── Apps ──────────────────────────────────────────────────────────
    ("mail-inbox.png",           "/mail/inbox/",                    True,  "light"),
    ("mail-thread.png",          "_first_mail",                     True,  "light"),
    ("chat.png",                 "_first_chat",                     True,  "light"),
    ("calendar.png",             "/calendar/",                      True,  "light"),
    ("kanban.png",               "/kanban/",                        True,  "light"),
    ("kanban-dark.png",          "/kanban/",                        True,  "dark"),
    ("files.png",                "/files/",                         True,  "light"),
    ("charts.png",               "/charts/",                        True,  "light"),
    ("charts-dark.png",          "/charts/",                        True,  "dark"),
    ("notifications.png",        "/notifications/",                 True,  "light"),

    # ── Projects ──────────────────────────────────────────────────────
    ("projects-list.png",        "/projects/",                      True,  "light"),
    ("projects-overview.png",    "_first_project_overview",         True,  "light"),
    ("projects-tasks.png",       "_first_project_tasks",            True,  "light"),
    ("projects-team.png",        "_first_project_team",             True,  "light"),
    ("projects-activity.png",    "_first_project_activity",         True,  "light"),

    # ── People / profiles ─────────────────────────────────────────────
    ("profiles-list.png",        "/people/",                        True,  "light"),
    ("profiles-overview.png",    "_first_person_overview",          True,  "light"),
    ("profiles-projects.png",    "_first_person_projects",          True,  "light"),
    ("profiles-connections.png", "_first_person_connections",       True,  "light"),

    # ── Activity log ──────────────────────────────────────────────────
    ("activity-list.png",        "/activity/",                      True,  "light"),

    # ── Billing ───────────────────────────────────────────────────────
    ("billing-overview.png",     "/billing/",                       True,  "light"),
    ("billing-plans.png",        "/billing/plans/",                 True,  "light"),
    ("billing-payment-methods.png", "/billing/payment-methods/",    True,  "light"),
    ("billing-cancel.png",       "/billing/cancel/",                True,  "light"),

    # ── Showcase galleries ────────────────────────────────────────────
    ("pages-forms.png",          "/pages/forms/",                   True,  "light"),
    ("pages-widgets.png",        "/pages/widgets/",                 True,  "light"),
    ("pages-datatable.png",      "/pages/datatable/",               True,  "light"),
    ("pages-api-docs.png",       "/pages/api-docs/",                True,  "light"),
    ("pages-maps.png",           "/pages/maps/",                    True,  "light"),

    # ── Settings ──────────────────────────────────────────────────────
    ("settings-2fa.png",         "/settings/two-factor/",           True,  "light"),
]


def login(page):
    page.goto(f"{BASE}/accounts/login/")
    # The dev login form has DEMO_MODE pre-filling — clear and refill
    # so the script is correct regardless of the auto-fill state.
    page.fill("#id_username", DEMO_USERNAME)
    page.fill("#id_password", DEMO_PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_url(f"{BASE}/")


def resolve_dynamic(path: str, page) -> str:
    """Resolve placeholder URLs that need a real PK/slug from the live DB."""
    if path == "_first_invoice":
        page.goto(f"{BASE}/invoices/")
        href = page.locator("table tbody a").first.get_attribute("href")
        return href
    if path == "_first_mail":
        page.goto(f"{BASE}/mail/inbox/")
        href = page.evaluate("""() => {
            const links = [...document.querySelectorAll('a[href*=\"/mail/\"]')];
            const thread = links.find(a => /\\/mail\\/\\d+\\//.test(a.getAttribute('href')||''));
            return thread ? thread.getAttribute('href') : null;
        }""")
        return href or "/mail/inbox/"
    if path == "_first_chat":
        page.goto(f"{BASE}/chat/")
        href = page.locator("aside ul li a").first.get_attribute("href")
        return href
    if path == "_first_post":
        page.goto(f"{BASE}/blog/")
        href = page.evaluate("""() => {
            const a = document.querySelector('article a[href^=\"/blog/\"]');
            return a ? a.getAttribute('href') : null;
        }""")
        return href or "/blog/"
    if path == "_first_help_article":
        page.goto(f"{BASE}/help/")
        href = page.evaluate("""() => {
            const a = document.querySelector('a[href^=\"/help/a/\"]');
            return a ? a.getAttribute('href') : null;
        }""")
        return href or "/help/"
    if path.startswith("_first_project"):
        page.goto(f"{BASE}/projects/")
        slug = page.evaluate("""() => {
            const a = document.querySelector('article a[href^=\"/projects/\"]');
            const href = a ? a.getAttribute('href') : '';
            const m = href.match(/^\\/projects\\/([^/]+)\\//);
            return m ? m[1] : '';
        }""")
        suffix = path.split("_first_project_", 1)[1]
        return f"/projects/{slug}/" + ("" if suffix == "overview" else f"{suffix}/")
    if path.startswith("_first_person"):
        page.goto(f"{BASE}/people/")
        username = page.evaluate("""() => {
            const a = document.querySelector('article a[href^=\"/people/\"]');
            const href = a ? a.getAttribute('href') : '';
            const m = href.match(/^\\/people\\/([^/]+)\\//);
            return m ? m[1] : '';
        }""")
        suffix = path.split("_first_person_", 1)[1]
        return f"/people/{username}/" + ("" if suffix == "overview" else f"{suffix}/")
    return path


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for filename, path, needs_login, theme in PAGES:
            ctx = browser.new_context(viewport=VIEWPORT)
            page = ctx.new_page()
            if theme == "dark":
                page.add_init_script("localStorage.setItem('theme', 'dark')")
            if needs_login:
                login(page)
            url = resolve_dynamic(path, page)
            full = f"{BASE}{url}" if url.startswith("/") else url
            try:
                page.goto(full, wait_until="networkidle")
            except Exception:
                page.goto(full)
            page.wait_for_timeout(900)  # give charts/HTMX/maps a moment
            out = OUT / filename
            page.screenshot(path=str(out),
                            clip={"x": 0, "y": 0,
                                  "width": VIEWPORT["width"],
                                  "height": VIEWPORT["height"]})
            print(f"  {filename}")
            ctx.close()
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
