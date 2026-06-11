"""Single source of truth for the docs sidebar.

Mirrors the Next.js Apex docs structure: groups of (title, url_name)
items, rendered by `templates/layouts/docs.html`. To add a page:

  1. Add a `path()` to `apps/docs/urls.py` with a `name=`.
  2. Add an entry below in the right group.

The active item is detected by URL-name match in the template, so
adding a page without registering a URL will throw a NoReverseMatch.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DocItem:
    title: str
    url_name: str   # e.g. "docs:installation" — resolved via {% url %}


@dataclass(frozen=True)
class DocGroup:
    title: str
    items: tuple[DocItem, ...]


DOCS_NAV: tuple[DocGroup, ...] = (
    DocGroup("Getting started", (
        DocItem("Introduction",     "docs:index"),
        DocItem("Installation",     "docs:installation"),
        DocItem("Folder structure", "docs:folder_structure"),
        DocItem("Architecture",     "docs:architecture"),
    )),
    DocGroup("Customization", (
        DocItem("Brand + tokens",   "docs:customize"),
        DocItem("Theming + dark mode", "docs:theming"),
        DocItem("Adding pages",     "docs:adding_pages"),
        DocItem("Components",       "docs:components"),
        DocItem("Charts",           "docs:charts"),
        DocItem("Internationalization", "docs:i18n"),
    )),
    DocGroup("Production", (
        DocItem("Deploy to Linux",  "docs:deployment"),
        DocItem("Demo mode + reseed", "docs:demo_mode"),
        DocItem("Backups",          "docs:backups"),
        DocItem("Health + monitoring", "docs:monitoring"),
    )),
    DocGroup("Reference", (
        DocItem("Realtime / Channels", "docs:realtime"),
        DocItem("API (Django Ninja)",  "docs:api"),
        DocItem("Organizations + RBAC", "docs:organizations"),
        DocItem("Testing",          "docs:testing"),
        DocItem("Changelog",        "docs:changelog"),
        DocItem("FAQ",              "docs:faq"),
    )),
)
