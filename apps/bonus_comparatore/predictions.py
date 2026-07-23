"""Aggregatore PRONOSTICI gratis da fonti pubbliche:
- Cassandra (RSS), Pronostici Calcio 365 (RSS) -> riuso _fetch_feed delle news
- SportyTrader (no RSS) -> si leggono solo i link+titolo delle schede partita,
  rimandando al loro sito (attribuzione + traffico a loro). Best-effort: se una
  fonte e' giu, viene saltata e la pagina non si rompe mai. Cache Redis 30 min.
"""
import datetime as _dt
import re
import urllib.request

from django.core.cache import cache
from django.utils import timezone

from .news import _fetch_feed  # riuso il parser RSS delle news

_UA = "Mozilla/5.0 (compatible; AblecoinPredictions/1.0; +https://ablecoin.it)"
_CACHE_KEY = "ablecoin_predictions_v1"
_CACHE_TTL = 1800  # 30 minuti

RSS_SOURCES = [
    ("Cassandra", "https://www.cassandrapronostici.com/feed/"),
]
_ST_URL = "https://www.sportytrader.it/pronostici/"
_ST_RE = re.compile(r'href="(https://www\.sportytrader\.it/pronostici/([a-z0-9-]+)-(\d+)/)"')


def _fetch_sportytrader(per_feed=6):
    req = urllib.request.Request(_ST_URL, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        htmltxt = r.read().decode("utf-8", "ignore")
    items, seen = [], set()
    for m in _ST_RE.finditer(htmltxt):
        link, slug = m.group(1), m.group(2)
        if link in seen:
            continue
        seen.add(link)
        title = "Pronostico " + slug.replace("-", " ").title()
        items.append({"title": title, "link": link,
                      "source": "SportyTrader", "image": "", "published": None})
        if len(items) >= per_feed:
            break
    return items


def fetch_predictions(limit=12, per_feed=6):
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached[:limit]
    per_source = []
    for name, url in RSS_SOURCES:
        try:
            per_source.append(_fetch_feed(name, url, per_feed))
        except Exception:  # noqa: BLE001
            per_source.append([])
    try:
        per_source.append(_fetch_sportytrader(per_feed))
    except Exception:  # noqa: BLE001
        per_source.append([])
    # alterna le fonti
    seen, merged, idx = set(), [], 0
    while any(idx < len(s) for s in per_source):
        for s in per_source:
            if idx < len(s):
                x = s[idx]
                k = x["title"].lower()
                if k not in seen:
                    seen.add(k)
                    merged.append(x)
        idx += 1
    # Rimuovi i pronostici vecchi: tieni solo quelli da OGGI in poi
    # (gli item senza data, es. SportyTrader, sono pagine correnti -> si tengono).
    # Un pronostico resta valido il giorno-partita; lo rimuoviamo quando la
    # partita e' stata giocata. Teniamo pubblicati da IERI in poi (1 giorno di
    # tolleranza per le schedine uscite la sera prima); i piu' vecchi spariscono.
    _cutoff = timezone.localdate() - _dt.timedelta(days=1)
    def _is_recent(x):
        p = x.get("published")
        if not p:
            return True
        try:
            return timezone.localtime(p).date() >= _cutoff
        except Exception:
            return True
    merged = [x for x in merged if _is_recent(x)]
    cache.set(_CACHE_KEY, merged, _CACHE_TTL)
    return merged[:limit]
