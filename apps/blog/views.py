"""Public blog views — anonymous browsing, no auth required."""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import Post, Topic


def _common_context():
    return {
        "topics_nav": Topic.objects.annotate(
            published_count=Count("posts", filter=Q(posts__is_published=True))
        ).filter(published_count__gt=0),
    }


def post_list(request):
    """Latest posts with featured-hero, topic chips, and search."""
    qs = Post.objects.filter(is_published=True).select_related("topic", "author")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q)
                       | Q(body__icontains=q))

    topic_slug = request.GET.get("topic", "")
    active_topic = None
    if topic_slug:
        active_topic = Topic.objects.filter(slug=topic_slug).first()
        if active_topic:
            qs = qs.filter(topic=active_topic)

    qs = qs.order_by("-published_at")
    featured = qs.filter(is_featured=True).first() if not (q or topic_slug) else None
    if featured:
        rest = qs.exclude(pk=featured.pk)
    else:
        rest = qs

    return render(request, "blog/list.html", {
        "featured": featured,
        "posts": rest,
        "q": q,
        "active_topic": active_topic,
        **_common_context(),
    })


def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True)
    post.increment_views()
    related = (
        Post.objects.filter(is_published=True, topic=post.topic)
        .exclude(pk=post.pk)
        .select_related("topic", "author")[:3]
    )
    return render(request, "blog/detail.html", {
        "post": post,
        "related": related,
        "breadcrumbs": [
            ("Blog", reverse("blog:list")),
            (post.title, None),
        ],
        **_common_context(),
    })


def topic_detail(request, slug):
    topic = get_object_or_404(Topic, slug=slug)
    posts = (Post.objects.filter(is_published=True, topic=topic)
             .select_related("author").order_by("-published_at"))
    return render(request, "blog/topic.html", {
        "topic": topic,
        "posts": posts,
        **_common_context(),
    })
