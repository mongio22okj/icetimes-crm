"""Risultati live da SportMonks API v3.

Cache 60s per rispettare i rate-limit del piano free.
Best-effort: se l'API non risponde la sezione sparisce senza rompere la pagina.
"""
import json
import urllib.request

from django.conf import settings
from django.core.cache import cache

_CACHE_KEY = "sportmonks_live_v1"
_CACHE_TTL = 60  # secondi


def _score(scores, side):
    """Estrae il punteggio (current period) per home o away."""
    for s in scores:
        sc = s.get("score", {})
        if sc.get("participant") == side and sc.get("sub") is None:
            return sc.get("goals", 0)
    return 0


def fetch_livescores():
    """Ritorna lista di partite live. Lista vuota se API giù o nessuna partita."""
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached

    token = getattr(settings, "SPORTMONKS_API_TOKEN", "")
    if not token:
        return []

    url = (
        "https://api.sportmonks.com/v3/football/livescores"
        f"?api_token={token}&include=scores;participants;league"
    )
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read())
    except Exception:
        return []

    matches = []
    for m in payload.get("data", []):
        parts = m.get("participants") or []
        home_p = next((p for p in parts if (p.get("meta") or {}).get("location") == "home"), {})
        away_p = next((p for p in parts if (p.get("meta") or {}).get("location") == "away"), {})

        scores = m.get("scores") or []
        state = m.get("state") or {}
        status = state.get("short_name") or state.get("developer_name") or "LIVE"
        minute = m.get("minute") or ""

        league = m.get("league") or {}
        league_name = league.get("name") or league.get("short_code") or ""

        matches.append({
            "home": home_p.get("name", "?"),
            "away": away_p.get("name", "?"),
            "home_score": _score(scores, "home"),
            "away_score": _score(scores, "away"),
            "status": status,
            "minute": minute,
            "league": league_name,
        })

    cache.set(_CACHE_KEY, matches, _CACHE_TTL)
    return matches


def fetch_todays_schedule():
    """Partite di oggi (incluse già finite), per mostrare anche il programma."""
    cache_key = "sportmonks_schedule_v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    token = getattr(settings, "SPORTMONKS_API_TOKEN", "")
    if not token:
        return []

    from datetime import date
    today = date.today().isoformat()
    url = (
        "https://api.sportmonks.com/v3/football/fixtures/date/" + today
        + f"?api_token={token}&include=scores;participants;league;state"
    )
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read())
    except Exception:
        return []

    matches = []
    for m in payload.get("data", []):
        parts = m.get("participants") or []
        home_p = next((p for p in parts if (p.get("meta") or {}).get("location") == "home"), {})
        away_p = next((p for p in parts if (p.get("meta") or {}).get("location") == "away"), {})

        scores = m.get("scores") or []
        state = m.get("state") or {}
        dev_name = (state.get("developer_name") or "").upper()
        status = state.get("short_name") or dev_name or "?"
        minute = m.get("minute") or ""
        starting_at = m.get("starting_at") or ""

        league = m.get("league") or {}
        league_name = league.get("name") or ""

        is_live = dev_name in ("INPLAY_1ST_HALF", "INPLAY_2ND_HALF", "HT", "EXTRA_TIME",
                               "PENALTY", "INPLAY_ET", "INPLAY_PENALTIES")
        is_finished = dev_name in ("FT", "AET", "FT_PEN", "AWARDED", "WO", "CANCELLED",
                                   "POSTPONED", "ABANDONED")

        matches.append({
            "home": home_p.get("name", "?"),
            "away": away_p.get("name", "?"),
            "home_score": _score(scores, "home") if (is_live or is_finished) else None,
            "away_score": _score(scores, "away") if (is_live or is_finished) else None,
            "status": status,
            "minute": minute,
            "league": league_name,
            "starting_at": starting_at,
            "is_live": is_live,
            "is_finished": is_finished,
        })

    cache.set(cache_key, matches, 60)
    return matches
