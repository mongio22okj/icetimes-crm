"""Aggregatore notizie calcio da feed RSS pubblici (Gazzetta, Corriere dello
Sport). Mostriamo solo titolo + fonte + data + link all'originale (no articoli
interi) → rispetto del copyright; i feed RSS sono pensati per la sindacazione.

Cache 15 minuti in Redis (default cache) per non interrogare le fonti a ogni
visita. Best-effort: se un feed non risponde, viene semplicemente saltato e la
pagina non si rompe mai.
"""
import html
import urllib.request
from datetime import timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from django.core.cache import cache

_UA = "Mozilla/5.0 (compatible; AblecoinNews/1.0; +https://ablecoin.it)"
_CACHE_KEY = "ablecoin_news_v1"
_CACHE_TTL = 900  # 15 minuti

# (nome mostrato, url feed RSS)
# NB: il feed Gazzetta è il "dynamic-feed" di sezione, che è cronologico e
# aggiornato in tempo reale; /rss/calcio.xml invece è editoriale e con date
# vecchie (fermo al 2023).
SOURCES = [
    ("Gazzetta", "https://www.gazzetta.it/dynamic-feed/rss/section/Calcio.xml"),
    ("Corriere dello Sport", "https://www.corrieredellosport.it/rss/calcio"),
]


def _item_image(it):
    """URL immagine da un <item>: prima <enclosure url>, poi qualsiasi tag
    in namespace media (media:thumbnail / media:content) con attributo url."""
    enc = it.find("enclosure")
    if enc is not None and enc.get("url"):
        return enc.get("url")
    for ch in it:
        tag = ch.tag.split("}")[-1]  # toglie il namespace
        if tag in ("thumbnail", "content") and ch.get("url"):
            return ch.get("url")
    return ""


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
        image = _item_image(it)
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

    # Ogni feed mantenuto nel suo ordine nativo (Gazzetta = ranking editoriale,
    # Corriere = cronologico). NON ordino globalmente per data, altrimenti la
    # Gazzetta (che ha date editoriali non recenti) sparirebbe sotto al
    # Corriere: invece ALTERNO le due fonti così appaiono entrambe.
    per_source = []
    for name, url in SOURCES:
        try:
            per_source.append(_fetch_feed(name, url, per_feed))
        except Exception:  # noqa: BLE001 — feed giù: si salta
            per_source.append([])

    seen, merged = set(), []
    idx = 0
    while any(idx < len(s) for s in per_source):
        for s in per_source:
            if idx < len(s):
                x = s[idx]
                key = x["title"].lower()
                if key not in seen:
                    seen.add(key)
                    merged.append(x)
        idx += 1

    cache.set(_CACHE_KEY, merged, _CACHE_TTL)
    return merged[:limit]
