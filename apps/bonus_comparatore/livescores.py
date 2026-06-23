import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache


def _curl(url, headers=None):
    cmd = ["curl", "-s", "--max-time", "8", "-A", "curl/7.81.0"]
    for h in (headers or []):
        cmd += ["-H", h]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(r.stderr[:200])
    return json.loads(r.stdout)


def _normalize(name):
    return re.sub(r"[^a-z ]", "", name.lower()).strip()


# ── football-data.org ────────────────────────────────────────────────────────

def _fd_label(status, minute=None):
    m = {"IN_PLAY": f"{minute}'" if minute else "LIVE", "PAUSED": "HT",
         "FINISHED": "FT", "SCHEDULED": "NS", "TIMED": "NS",
         "POSTPONED": "RINV", "CANCELLED": "CANC", "SUSPENDED": "SOSP"}
    return m.get(status, status)


def _fd_parse(matches):
    out = []
    for m in matches:
        status = m.get("status", "")
        minute = m.get("minute")
        is_live = status in ("IN_PLAY", "PAUSED")
        is_fin = status == "FINISHED"
        ft = (m.get("score") or {}).get("fullTime") or {}
        home = m.get("homeTeam") or {}
        away = m.get("awayTeam") or {}
        comp = m.get("competition") or {}
        out.append({
            "home": home.get("name", "?"), "away": away.get("name", "?"),
            "home_logo": home.get("crest", ""), "away_logo": away.get("crest", ""),
            "home_score": ft.get("home") if (is_live or is_fin) else None,
            "away_score": ft.get("away") if (is_live or is_fin) else None,
            "status": _fd_label(status, minute), "minute": minute or "",
            "league": comp.get("name", ""), "league_logo": comp.get("emblem", ""),
            "starting_at": m.get("utcDate", ""), "is_live": is_live, "is_finished": is_fin,
        })
    return out


def _fetch_fd():
    token = getattr(settings, "FOOTBALL_DATA_API_TOKEN", "")
    if not token:
        return []
    h = [f"X-Auth-Token: {token}"]
    base = "https://api.football-data.org/v4"
    today = date.today().isoformat()
    try:
        live = _fd_parse(_curl(f"{base}/matches?status=IN_PLAY", h).get("matches") or [])
    except Exception:
        live = []
    try:
        all_today = _fd_parse(_curl(f"{base}/matches?dateFrom={today}&dateTo={today}", h).get("matches") or [])
    except Exception:
        all_today = []
    seen = {(_normalize(m["home"]), _normalize(m["away"])) for m in live}
    return live + [m for m in all_today if (_normalize(m["home"]), _normalize(m["away"])) not in seen]


# ── api-football / api-sports.io ─────────────────────────────────────────────

def _af_label(short, elapsed=None):
    live_shorts = {"1H", "HT", "2H", "ET", "BT", "P", "INT"}
    if short in live_shorts and elapsed:
        return f"{elapsed}'"
    m = {"1H": "1T", "HT": "HT", "2H": "2T", "ET": "ET", "P": "RIG",
         "FT": "FT", "AET": "FT", "PEN": "FT", "NS": "NS",
         "PST": "RINV", "CANC": "CANC", "ABD": "SOSP", "AWD": "FT", "WO": "FT"}
    return m.get(short, short or "NS")


def _af_parse(response):
    out = []
    for m in response:
        fix = m.get("fixture") or {}
        teams = m.get("teams") or {}
        goals = m.get("goals") or {}
        league = m.get("league") or {}
        st = fix.get("status") or {}
        short = st.get("short", "NS")
        elapsed = st.get("elapsed")
        is_live = short in ("1H", "HT", "2H", "ET", "BT", "P", "INT")
        is_fin = short in ("FT", "AET", "PEN", "AWD", "WO")
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        out.append({
            "home": home.get("name", "?"), "away": away.get("name", "?"),
            "home_logo": home.get("logo", ""), "away_logo": away.get("logo", ""),
            "home_score": goals.get("home") if (is_live or is_fin) else None,
            "away_score": goals.get("away") if (is_live or is_fin) else None,
            "status": _af_label(short, elapsed), "minute": elapsed or "",
            "league": league.get("name", ""), "league_logo": league.get("logo", ""),
            "starting_at": fix.get("date", ""), "is_live": is_live, "is_finished": is_fin,
            "fixture_id": fix.get("id"), "_src": "af",
        })
    return out


def _fetch_af():
    token = getattr(settings, "API_FOOTBALL_TOKEN", "")
    if not token:
        return []
    h = [f"x-apisports-key: {token}"]
    base = "https://v3.football.api-sports.io"
    today = date.today().isoformat()
    try:
        live = _af_parse(_curl(f"{base}/fixtures?live=all", h).get("response") or [])
    except Exception:
        live = []
    try:
        all_today = _af_parse(_curl(f"{base}/fixtures?date={today}", h).get("response") or [])
    except Exception:
        all_today = []
    seen = {(_normalize(m["home"]), _normalize(m["away"])) for m in live}
    return live + [m for m in all_today if (_normalize(m["home"]), _normalize(m["away"])) not in seen]


# ── allsportsapi.com ─────────────────────────────────────────────────────────

def _as_label(status):
    s = str(status or "").strip()
    if s.isdigit():
        return f"{s}'"
    m = {"Finished": "FT", "Half Time": "HT", "Not Started": "NS",
         "Postponed": "RINV", "Cancelled": "CANC", "Suspended": "SOSP",
         "Extra Time": "ET", "Penalty In Progress": "RIG"}
    return m.get(s, s or "NS")


def _as_parse(result):
    out = []
    for m in (result or []):
        sr = m.get("event_status", "")
        is_live = str(sr).isdigit() or sr in ("Half Time", "Extra Time", "Penalty In Progress")
        is_fin = sr == "Finished"
        out.append({
            "home": m.get("event_home_team", "?"), "away": m.get("event_away_team", "?"),
            "home_logo": m.get("home_team_logo", ""), "away_logo": m.get("away_team_logo", ""),
            "home_score": m.get("event_home_final_result") if (is_live or is_fin) else None,
            "away_score": m.get("event_away_final_result") if (is_live or is_fin) else None,
            "status": _as_label(sr), "minute": str(sr) if str(sr).isdigit() else "",
            "league": m.get("league_name", ""), "league_logo": m.get("league_logo", ""),
            "starting_at": f"{m.get('event_date', '')}T{m.get('event_time', '00:00')}:00",
            "is_live": is_live, "is_finished": is_fin,
        })
    return out


def _fetch_as():
    token = getattr(settings, "ALLSPORTS_API_TOKEN", "")
    if not token:
        return []
    base = f"https://apiv2.allsportsapi.com/football/?APIkey={token}"
    today = date.today().isoformat()
    try:
        live = _as_parse(_curl(f"{base}&met=Livescore").get("result") or [])
    except Exception:
        live = []
    try:
        all_today = _as_parse(_curl(f"{base}&met=Fixtures&from={today}&to={today}").get("result") or [])
    except Exception:
        all_today = []
    seen = {(_normalize(m["home"]), _normalize(m["away"])) for m in live}
    return live + [m for m in all_today if (_normalize(m["home"]), _normalize(m["away"])) not in seen]


# ── aggregatore principale ────────────────────────────────────────────────────

def fetch_todays_schedule():
    cache_key = "agg_schedule_v2"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    all_matches = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(f) for f in (_fetch_fd, _fetch_af, _fetch_as)]
        for fut in as_completed(futures):
            try:
                all_matches.extend(fut.result())
            except Exception:
                pass

    # Deduplicazione: per stessa coppia di squadre tieni il più informativo
    seen = {}
    for m in all_matches:
        key = (_normalize(m["home"]), _normalize(m["away"]))
        if key not in seen:
            seen[key] = m
        else:
            ex = seen[key]
            if (m["home_score"] is not None and ex["home_score"] is None) or \
               (m["is_live"] and not ex["is_live"]):
                seen[key] = m

    matches = list(seen.values())
    matches.sort(key=lambda x: (not x["is_live"], not x["is_finished"], x["starting_at"]))

    # Fallback prossimi 7 giorni se oggi vuoto
    if not matches:
        today = date.today().isoformat()
        end = (date.today() + timedelta(days=7)).isoformat()
        try:
            token = getattr(settings, "FOOTBALL_DATA_API_TOKEN", "")
            upcoming = _fd_parse(
                _curl(f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={end}",
                      [f"X-Auth-Token: {token}"]).get("matches") or []
            )
            upcoming.sort(key=lambda x: x["starting_at"])
            matches = upcoming[:30]
        except Exception:
            matches = []

    ttl = 30 if any(m["is_live"] for m in matches) else 120
    cache.set(cache_key, matches, ttl)
    return matches
