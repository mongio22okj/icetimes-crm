import json

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, View

from .models import Bookmaker, ClickLog


def _client_ip(request):
    """IP reale del visitatore. Il sito è dietro Cloudflare → l'IP vero è in
    CF-Connecting-IP; fallback su X-Forwarded-For (primo hop) e REMOTE_ADDR."""
    ip = request.META.get("HTTP_CF_CONNECTING_IP")
    if not ip:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
    return ip or None


class BonusHomeView(ListView):
    template_name = "bonus_comparatore/home.html"
    context_object_name = "bookmakers"

    def get_queryset(self):
        category = self.request.GET.get("c", "")
        qs = Bookmaker.objects.filter(is_published=True).prefetch_related("bonuses")
        if category in {"sport", "casino"}:
            qs = qs.filter(category__in=[category, "both"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_category"] = self.request.GET.get("c", "")
        # Notizie calcio (best-effort: mai bloccare la pagina se i feed sono giù)
        try:
            from .news import fetch_news
            ctx["news"] = fetch_news(limit=9)
        except Exception:  # noqa: BLE001
            ctx["news"] = []
        return ctx


class BookmakerDetailView(DetailView):
    model = Bookmaker
    template_name = "bonus_comparatore/bookmaker_detail.html"
    context_object_name = "bookmaker"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Bookmaker.objects.filter(is_published=True).prefetch_related("bonuses")


class BookmakerGoView(View):
    """Redirect tracciato verso il link affiliato (o ufficiale, se manca)."""

    def get(self, request, slug):
        bm = get_object_or_404(Bookmaker, slug=slug, is_published=True)
        # Registra il click in uscita (best-effort: non deve mai bloccare il
        # redirect verso il bookmaker se il logging fallisce).
        try:
            ClickLog.objects.create(
                bookmaker=bm,
                ip=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
                referer=request.META.get("HTTP_REFERER", "")[:500],
                to_affiliate=bm.has_affiliate,
            )
        except Exception:  # noqa: BLE001
            pass
        return HttpResponseRedirect(bm.target_url)


class MatchDetailApiView(View):
    """Dettaglio partita: marcatori, statistiche, formazioni via api-football."""

    def get(self, request):
        fixture_id = request.GET.get("id", "")
        if not fixture_id or not fixture_id.isdigit():
            return HttpResponse(json.dumps({"error": "invalid id"}), content_type="application/json", status=400)

        from django.conf import settings
        token = getattr(settings, "API_FOOTBALL_TOKEN", "")
        if not token:
            return HttpResponse(json.dumps({"error": "no token"}), content_type="application/json", status=503)

        import subprocess
        h = f"x-apisports-key: {token}"
        base = f"https://v3.football.api-sports.io"

        def fetch(url):
            r = subprocess.run(
                ["curl", "-s", "--max-time", "8", "-H", h, url],
                capture_output=True, text=True, timeout=10,
            )
            return json.loads(r.stdout) if r.stdout.strip() else {}

        try:
            events_raw = fetch(f"{base}/fixtures/events?fixture={fixture_id}").get("response") or []
            stats_raw = fetch(f"{base}/fixtures/statistics?fixture={fixture_id}").get("response") or []
            lineups_raw = fetch(f"{base}/fixtures/lineups?fixture={fixture_id}").get("response") or []
        except Exception as e:
            return HttpResponse(json.dumps({"error": str(e)}), content_type="application/json", status=502)

        # Marcatori / eventi
        events = []
        for ev in events_raw:
            t = ev.get("type", "")
            detail = ev.get("detail", "")
            player = (ev.get("player") or {}).get("name", "")
            assist = (ev.get("assist") or {}).get("name", "")
            team = (ev.get("team") or {}).get("name", "")
            minute = (ev.get("time") or {}).get("elapsed", "")
            extra = (ev.get("time") or {}).get("extra")
            min_str = f"{minute}+{extra}'" if extra else f"{minute}'"
            if t in ("Goal", "subst", "Card"):
                events.append({
                    "type": t, "detail": detail, "player": player,
                    "assist": assist, "team": team, "minute": min_str,
                })

        # Statistiche
        stats = []
        for side in stats_raw:
            team_name = (side.get("team") or {}).get("name", "")
            vals = {s["type"]: s["value"] for s in (side.get("statistics") or [])}
            stats.append({"team": team_name, "stats": vals})

        # Formazioni
        lineups = []
        for side in lineups_raw:
            team_name = (side.get("team") or {}).get("name", "")
            team_logo = (side.get("team") or {}).get("logo", "")
            formation = side.get("formation", "")
            starters = [p.get("player", {}).get("name", "") for p in (side.get("startXI") or [])]
            subs = [p.get("player", {}).get("name", "") for p in (side.get("substitutes") or [])]
            lineups.append({"team": team_name, "logo": team_logo, "formation": formation,
                            "starters": starters, "subs": subs})

        return HttpResponse(
            json.dumps({"events": events, "stats": stats, "lineups": lineups}, default=str),
            content_type="application/json",
        )


class NewsApiView(View):
    """JSON endpoint per le notizie sportive (polling JS ogni 5 min)."""

    def get(self, request):
        try:
            from .news import fetch_news
            # forza refresh se richiesto esplicitamente
            if request.GET.get("refresh") == "1":
                from django.core.cache import cache
                cache.delete("ablecoin_news_v1")
            items = fetch_news(limit=12)
        except Exception:
            items = []
        # serializza datetime in stringa
        out = []
        for n in items:
            out.append({
                "title": n.get("title", ""),
                "link": n.get("link", ""),
                "source": n.get("source", ""),
                "image": n.get("image", ""),
                "published": n["published"].strftime("%d/%m · %H:%M") if n.get("published") else "",
            })
        return HttpResponse(json.dumps({"news": out}), content_type="application/json")


class LiveScoresApiView(View):
    """JSON endpoint per il widget risultati live (polling JS ogni 60s)."""

    def get(self, request):
        try:
            from .livescores import fetch_todays_schedule
            matches = fetch_todays_schedule()
        except Exception:
            matches = []
        return HttpResponse(
            json.dumps({"matches": matches}, default=str),
            content_type="application/json",
        )
