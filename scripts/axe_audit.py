"""Axe-core accessibility audit across key pages.

Loads axe-core from CDN, runs it in each page, and reports violations
grouped by impact level (critical / serious / moderate / minor).

    uv run python scripts/axe_audit.py
"""
from collections import defaultdict

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.0/axe.min.js"

PAGES = [
    ("login",          "/accounts/login/",     False),
    ("dashboard",      "/",                    True),
    ("invoices",       "/invoices/",           True),
    ("invoice-detail", "_first_invoice",       True),
    ("customers",      "/customers/",          True),
    ("mail",           "/mail/inbox/",         True),
    ("chat",           "/chat/",               True),
    ("calendar",       "/calendar/",           True),
    ("kanban",         "/kanban/",             True),
    ("files",          "/files/",              True),
    ("charts",         "/charts/",             True),
    ("landing-hub",    "/landing/",            False),
    ("pricing",        "/landing/pricing/",    False),
]


def login(page):
    page.goto(f"{BASE}/accounts/login/")
    page.fill("#id_username", "demo")
    page.fill("#id_password", "demo1234")
    page.click("button[type=submit]")
    page.wait_for_url(f"{BASE}/")


def resolve_dynamic(path: str, page) -> str:
    if path == "_first_invoice":
        page.goto(f"{BASE}/invoices/")
        href = page.locator("table tbody a").first.get_attribute("href")
        return href or "/invoices/"
    return path


def main():
    rollup = defaultdict(list)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for slug, path, needs_login in PAGES:
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            if needs_login:
                login(page)
            url = resolve_dynamic(path, page)
            page.goto(f"{BASE}{url}", wait_until="networkidle")
            page.wait_for_timeout(500)
            page.add_script_tag(url=AXE_CDN)
            results = page.evaluate("""
                async () => {
                    const r = await window.axe.run(document, {
                        runOnly: { type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice'] }
                    });
                    return r.violations.map(v => ({
                        id: v.id,
                        impact: v.impact,
                        help: v.help,
                        nodes: v.nodes.length,
                        sample: (v.nodes[0]||{}).target,
                    }));
                }
            """)
            ctx.close()
            for v in results:
                rollup[v["impact"]].append({"page": slug, **v})

        browser.close()

    # Pretty report
    order = ["critical", "serious", "moderate", "minor", None]
    for level in order:
        if level not in rollup or not rollup[level]:
            continue
        print(f"\n=== {level or 'unknown'} ({len(rollup[level])}) ===")
        # Group by rule id
        by_rule = defaultdict(list)
        for v in rollup[level]:
            by_rule[v["id"]].append(v)
        for rule_id, vs in sorted(by_rule.items(), key=lambda x: -len(x[1])):
            pages = sorted({v["page"] for v in vs})
            sample = vs[0]
            total_nodes = sum(v["nodes"] for v in vs)
            print(f"  {rule_id}  ({total_nodes} elements across {len(pages)} pages: {', '.join(pages)})")
            print(f"    {sample['help']}")
            print(f"    e.g. {sample['sample']}")


if __name__ == "__main__":
    main()
