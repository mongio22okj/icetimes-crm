from django.http import HttpResponseRedirect
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
