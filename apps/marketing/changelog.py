"""Parse the project's CHANGELOG.md into release entries for /changelog/.

We treat the file as the single source of truth — no DB model.
Releases are split on the `## [version] - date` headings; each entry's
markdown body is rendered with a small handwritten markdown converter
(no extra dep needed for the limited subset we use: headings, lists,
inline code, bold, links).

Cached in-process for the lifetime of the worker — the file changes
only on deploy, so re-reading on every request is wasteful but safe.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings

CHANGELOG_PATH = Path(settings.BASE_DIR) / "CHANGELOG.md"

# `## [0.13.0] - 2026-04-29` — version + date
RELEASE_HEADING_RE = re.compile(
    r"^##\s+\[([^\]]+)\]\s*-\s*(\d{4}-\d{2}-\d{2})\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Release:
    version: str            # "0.14.0"
    date: str               # "2026-04-29"
    summary: str            # one-paragraph blurb after the heading
    body_html: str          # rendered markdown body
    anchor: str             # url-safe slug (e.g. "v0-14-0")


@lru_cache(maxsize=1)
def parse_changelog() -> list[Release]:
    if not CHANGELOG_PATH.exists():
        return []
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    # Split on release headings while keeping the heading itself.
    headings = list(RELEASE_HEADING_RE.finditer(text))
    if not headings:
        return []
    releases: list[Release] = []
    for i, m in enumerate(headings):
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body_md = text[start:end].strip()
        version = m.group(1).strip()
        date = m.group(2).strip()
        summary = _extract_first_paragraph(body_md)
        releases.append(Release(
            version=version,
            date=date,
            summary=summary,
            body_html=_render_markdown(body_md),
            anchor=f"v{version.replace('.', '-')}",
        ))
    return releases


def _extract_first_paragraph(md: str) -> str:
    """First non-empty paragraph after the heading, stripped of markdown."""
    for chunk in md.split("\n\n"):
        chunk = chunk.strip()
        if not chunk or chunk.startswith("#"):
            continue
        # Strip inline code + emphasis for the summary line.
        return re.sub(r"`([^`]+)`", r"\1", chunk).replace("**", "").strip()
    return ""


def _render_markdown(md: str) -> str:
    """Tiny markdown → HTML converter for the changelog subset.

    Handles: H3 headings, bullet lists (- and *), inline code, **bold**,
    `code spans`, [text](url) links, paragraphs. Anything fancier and
    we'd reach for the `markdown` package — but the changelog is
    deliberately simple.
    """
    out_lines: list[str] = []
    in_list = False
    for raw_line in md.splitlines():
        line = raw_line.rstrip()
        if not line:
            if in_list:
                out_lines.append("</ul>")
                in_list = False
            out_lines.append("")
            continue
        if line.startswith("### "):
            if in_list:
                out_lines.append("</ul>")
                in_list = False
            out_lines.append(
                f'<h3 class="text-base font-semibold mt-6 mb-2">{_inline(line[4:])}</h3>',
            )
            continue
        if line.startswith("- ") or line.startswith("* "):
            if not in_list:
                out_lines.append('<ul class="space-y-1.5 my-2 ml-5 list-disc text-sm text-muted-foreground marker:text-muted-foreground/50">')
                in_list = True
            out_lines.append(f"  <li>{_inline(line[2:])}</li>")
            continue
        if line.startswith("```"):
            # Code blocks aren't used in the changelog body — skip the fence.
            continue
        if in_list and line.startswith("  "):
            # Indented continuation of the previous list item.
            out_lines[-1] = out_lines[-1].replace("</li>",
                                                  f" {_inline(line.strip())}</li>")
            continue
        if in_list:
            out_lines.append("</ul>")
            in_list = False
        out_lines.append(f'<p class="text-sm text-muted-foreground my-2">{_inline(line)}</p>')
    if in_list:
        out_lines.append("</ul>")
    return "\n".join(out_lines)


def _inline(text: str) -> str:
    """Inline transforms: bold, code, links."""
    # Order matters — escape first, then re-introduce HTML, then transform.
    text = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
    # Inline code → <code>
    text = re.sub(
        r"`([^`]+)`",
        r'<code class="text-[11px] bg-muted px-1 py-0.5 rounded">\1</code>',
        text,
    )
    # Bold → <strong>
    text = re.sub(
        r"\*\*([^*]+)\*\*",
        r'<strong class="font-semibold text-foreground">\1</strong>',
        text,
    )
    # Links [text](url) → anchor
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" class="text-primary hover:underline">\1</a>',
        text,
    )
    return text
