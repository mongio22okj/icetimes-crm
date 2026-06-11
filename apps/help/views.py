"""Help center views — public, no auth required.

The home page surfaces popular + featured articles plus a category grid.
Category and article pages support full-text search across the corpus.
"""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import escape

from .models import Article, Category


def _common_context():
    return {
        "categories_nav": Category.objects.annotate(
            published_count=Count("articles", filter=Q(articles__is_published=True))
        ).filter(published_count__gt=0),
    }


def home(request):
    """Help home: search box, featured grid, popular articles, category cards."""
    q = request.GET.get("q", "").strip()
    if q:
        return search(request)

    featured = Article.objects.filter(is_published=True, is_featured=True)[:3]
    popular = (
        Article.objects.filter(is_published=True)
        .order_by("-view_count")[:8]
    )
    categories = Category.objects.annotate(
        published_count=Count("articles", filter=Q(articles__is_published=True))
    ).filter(published_count__gt=0)
    return render(request, "help/home.html", {
        "featured": featured,
        "popular": popular,
        "categories": categories,
        "breadcrumbs": [("Help center", None)],
        **_common_context(),
    })


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    articles = category.articles.filter(is_published=True)
    return render(request, "help/category.html", {
        "category": category,
        "articles": articles,
        "breadcrumbs": [
            ("Help center", reverse("help_center:home")),
            (category.name, None),
        ],
        **_common_context(),
    })


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    article.increment_views()
    related = (
        Article.objects.filter(category=article.category, is_published=True)
        .exclude(pk=article.pk)[:4]
    )
    return render(request, "help/article.html", {
        "article": article,
        "related": related,
        "breadcrumbs": [
            ("Help center", reverse("help_center:home")),
            (article.category.name, reverse(
                "help_center:category", args=[article.category.slug],
            )),
            (article.title, None),
        ],
        **_common_context(),
    })


def search(request):
    q = request.GET.get("q", "").strip()
    results = []
    if q:
        results = Article.objects.filter(is_published=True).filter(
            Q(title__icontains=q) | Q(summary__icontains=q) | Q(body__icontains=q)
        ).select_related("category")[:30]
    return render(request, "help/search.html", {
        "q": q,
        "results": results,
        "highlight": _highlight(q),
        "breadcrumbs": [
            ("Help center", reverse("help_center:home")),
            (f'Search "{q}"' if q else "Search", None),
        ],
        **_common_context(),
    })


def _highlight(q: str):
    """Return a closure usable as a template filter — wraps matches in <mark>."""
    if not q:
        return lambda s: s
    needle = q.lower()

    def render_highlighted(text: str) -> str:
        if not text:
            return ""
        escaped = escape(text)
        # Naive case-insensitive highlight over the escaped text
        out = []
        cursor = 0
        lower = escaped.lower()
        while True:
            i = lower.find(needle, cursor)
            if i < 0:
                out.append(escaped[cursor:])
                break
            out.append(escaped[cursor:i])
            out.append('<mark class="bg-amber-200 rounded px-0.5">')
            out.append(escaped[i:i + len(needle)])
            out.append("</mark>")
            cursor = i + len(needle)
        return "".join(out)

    return render_highlighted
