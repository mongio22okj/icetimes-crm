"""Aggregatore notizie calcio da feed RSS pubblici (Gazzetta, Corriere dello
Sport). Mostriamo solo titolo + fonte + data + link all'originale (no articoli
interi) → rispetto del copyright; i feed RSS sono pensati per la sindacazione.

Cache 15 minuti in Redis (default cache) per non interrogare le fonti a ogni
visita. Best-effort: se un feed non risponde, viene semplicemente saltato e la
pagina non si rompe mai.
"""
import html
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from django.core.cache import cache

_UA = "Mozilla/5.0 (compatible; AblecoinNews/1.0; +https://ablecoin.it)"
_CACHE_KEY = "ablecoin_news_v1"
_CACHE_TTL = 900  # 15 minuti

# (nome mostrato, url feed RSS)
SOURCES = [
    ("Gazzetta", "https://www.gazzetta.it/rss/calcio.xml"),
    ("Corriere dello Sport", "https://www.corrieredellosport.it/rss/calcio"),
]


def _parse_date(raw):
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _fetch_feed(name, url, per_feed):
    req = urllib.request.Request(
        url, headers={"User-Agent": _UA,
                      "Accept": "application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    items = []
    for it in root.iter("item"):
        # I feed codificano le entità dentro il CDATA (es. "l&#39;addio"):
        # html.unescape le riporta a caratteri reali, poi Django ri-escapa in
        # modo sicuro al render.
        title = html.unescape((it.findtext("title") or "").strip())
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        enc = it.find("enclosure")
        image = (enc.get("url") if enc is not None else "") or ""
        items.append({
            "title": title,
            "link": link,
            "source": name,
            "image": image,
            "published": _parse_date(it.findtext("pubDate")),
        })
        if len(items) >= per_feed:
            break
    return items


def fetch_news(limit=9, per_feed=8):
    """Ritorna una lista di notizie (dict) ordinate dalla più recente.

    Struttura item: title, link, source, image, published (datetime|None).
    """
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached[:limit]

    collected = []
    for name, url in SOURCES:
        try:
            collected.extend(_fetch_feed(name, url, per_feed))
        except Exception:  # noqa: BLE001 — feed giù: si salta
            continue

    _floor = datetime.min.replace(tzinfo=timezone.utc)
    collected.sort(key=lambda x: x["published"] or _floor, reverse=True)

    # de-dup per titolo (le due testate a volte rilanciano la stessa notizia)
    seen, merged = set(), []
    for x in collected:
        key = x["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(x)

    cache.set(_CACHE_KEY, merged, _CACHE_TTL)
    return merged[:limit]
