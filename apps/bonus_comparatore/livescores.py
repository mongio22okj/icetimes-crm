"""Risultati live da SportMonks API v3.

Cache 60s per rispettare i rate-limit del piano free.
Best-effort: se l'API non risponde la sezione sparisce senza rompere la pagina.
"""
import json
import subprocess

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
    """Partite attualmente in gioco (inplay). Lista vuota se API giù o pausa."""
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached

    token = getattr(settings, "SPORTMONKS_API_TOKEN", "")
    if not token:
        return []

    try:
        payload = _fetch_json(
            f"https://api.sportmonks.com/v3/football/livescores"
            f"?api_token={token}&include=scores;participants;league;state"
        )
    except Exception:
        return []
    # _fetch_json usa curl che bypassa il blocco Python-urllib di SportMonks

    matches = _parse_fixtures(payload.get("data") or [])

    cache.set(_CACHE_KEY, matches, _CACHE_TTL)
    return matches


def _parse_fixtures(data):
    """Converte la lista raw SportMonks in lista di dict normalizzati."""
    matches = []
    for m in data:
        parts = m.get("participants") or []
        home_p = next((p for p in parts if (p.get("meta") or {}).get("location") == "home"), {})
        away_p = next((p for p in parts if (p.get("meta") or {}).get("location") == "away"), {})

        scores = m.get("scores") or []
        state = m.get("state") or {}
        dev_name = (state.get("developer_name") or "").upper()
        # state_id=5 → FT (partita finita) per i fixture storici senza state include
        if not dev_name and m.get("state_id") == 5:
            dev_name = "FT"
        status = state.get("short_name") or dev_name or "NS"
        minute = m.get("minute") or ""
        starting_at = (m.get("starting_at") or "").replace(" ", "T")

        league = m.get("league") or {}
        league_name = league.get("name") or ""
        league_logo = league.get("image_path") or ""

        home_logo = home_p.get("image_path") or ""
        away_logo = away_p.get("image_path") or ""

        is_live = dev_name in ("INPLAY_1ST_HALF", "INPLAY_2ND_HALF", "HT", "EXTRA_TIME",
                               "PENALTY", "INPLAY_ET", "INPLAY_PENALTIES")
        is_finished = dev_name in ("FT", "AET", "FT_PEN", "AWARDED", "WO",
                                   "CANCELLED", "POSTPONED", "ABANDONED")

        matches.append({
            "home": home_p.get("name", "?"),
            "away": away_p.get("name", "?"),
            "home_logo": home_logo,
            "away_logo": away_logo,
            "home_score": _score(scores, "home") if (is_live or is_finished) else None,
            "away_score": _score(scores, "away") if (is_live or is_finished) else None,
            "status": status,
            "minute": minute,
            "league": league_name,
            "league_logo": league_logo,
            "starting_at": starting_at,
            "is_live": is_live,
            "is_finished": is_finished,
        })
    return matches


def _fetch_json(url):
    """SportMonks blocca Python-urllib con 403; usiamo subprocess curl."""
    result = subprocess.run(
        ["curl", "-s", "--max-time", "10", "-A", "curl/7.81.0", url],
        capture_output=True, text=True, timeout=12,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"curl failed: {result.stderr[:200]}")
    return json.loads(result.stdout)


def fetch_todays_schedule():
    """Partite di oggi. Se nessuna, mostra le prossime in programma (max 30 giorni)."""
    cache_key = "sportmonks_schedule_v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    token = getattr(settings, "SPORTMONKS_API_TOKEN", "")
    if not token:
        return []

    from datetime import date, timedelta
    today = date.today()
    base = f"?api_token={token}&include=scores;participants;league;state"

    # 1) Partite di oggi (programma completo + risultati in corso)
    try:
        payload = _fetch_json(
            f"https://api.sportmonks.com/v3/football/fixtures/date/{today.isoformat()}{base}"
        )
        matches = _parse_fixtures(payload.get("data") or [])
        matches.sort(key=lambda x: x["starting_at"])
    except Exception:
        matches = []

    # 3) Se oggi è vuoto, cerca le prossime partite nei prossimi 90 giorni
    if not matches:
        end = today + timedelta(days=90)
        try:
            payload = _fetch_json(
                f"https://api.sportmonks.com/v3/football/fixtures/between"
                f"/{today.isoformat()}/{end.isoformat()}{base}&per_page=20"
            )
            upcoming = _parse_fixtures(payload.get("data") or [])
            upcoming.sort(key=lambda x: x["starting_at"])
            matches = upcoming[:16]
        except Exception:
            matches = []

    # 4) Se ancora vuoto (off-season totale), mostra gli ultimi risultati
    if not matches:
        start = today - timedelta(days=14)
        try:
            payload = _fetch_json(
                f"https://api.sportmonks.com/v3/football/fixtures/between"
                f"/{start.isoformat()}/{today.isoformat()}{base}&per_page=20"
            )
            recent = _parse_fixtures(payload.get("data") or [])
            recent.sort(key=lambda x: x["starting_at"], reverse=True)
            for m in recent:
                m["_recent"] = True  # flag per il template
            matches = recent[:16]
        except Exception:
            matches = []

    ttl = 60 if any(m["is_live"] for m in matches) else 300
    cache.set(cache_key, matches, ttl)
    return matches
