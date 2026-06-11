"""Capture each key page at mobile (375) + tablet (768) widths to find breakage.

    uv run python scripts/capture_responsive.py
"""
import pathlib

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots/responsive"
OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://localhost:8000"

VIEWPORTS = [
    ("mobile",  375, 800),
    ("tablet",  768, 900),
]

PAGES = [
    ("landing-hub",       "/landing/",                  False),
    ("landing-pricing",   "/landing/pricing/",          False),
    ("login",             "/accounts/login/",           False),
    ("dashboard",         "/",                          True),
    ("invoices",          "/invoices/",                 True),
    ("customers",         "/customers/",                True),
    ("mail",              "/mail/inbox/",               True),
    ("chat",              "_first_chat",                True),
    ("calendar",          "/calendar/",                 True),
    ("kanban",            "/kanban/",                   True),
    ("files",             "/files/",                    True),
    ("charts",            "/charts/",                   True),
]


def login(page):
    page.goto(f"{BASE}/accounts/login/")
    page.fill("#id_username", "demo")
    page.fill("#id_password", "demo1234")
    page.click("button[type=submit]")
    page.wait_for_url(f"{BASE}/")


def resolve(path, page):
    if path == "_first_chat":
        page.goto(f"{BASE}/chat/")
        href = page.locator("aside ul li a").first.get_attribute("href") or "/chat/"
        return href
    return path


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, w, h in VIEWPORTS:
            for slug, path, needs_login in PAGES:
                ctx = browser.new_context(viewport={"width": w, "height": h})
                page = ctx.new_page()
                if needs_login:
                    login(page)
                url = resolve(path, page)
                page.goto(f"{BASE}{url}", wait_until="networkidle")
                page.wait_for_timeout(500)
                out = OUT / f"{slug}-{name}.png"
                page.screenshot(path=str(out), full_page=False)
                print(f"  ✓ {name}/{slug}")
                ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
