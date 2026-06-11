import pytest

from apps.blog.models import Post, Topic

pytestmark = pytest.mark.django_db


@pytest.fixture
def topic():
    return Topic.objects.create(name="Product", accent="#16a34a")


# ── List ──────────────────────────────────────────────────────────────

def test_list_renders_for_anon(client):
    r = client.get("/blog/")
    assert r.status_code == 200
    assert b"Blog" in r.content


def test_list_shows_published_posts(client, topic):
    Post.objects.create(title="VisiblePost", summary="s", body="x", topic=topic)
    Post.objects.create(title="HiddenPost",  summary="s", body="x",
                        topic=topic, is_published=False)
    r = client.get("/blog/")
    assert b"VisiblePost" in r.content
    assert b"HiddenPost" not in r.content


def test_list_promotes_featured_to_hero(client, topic):
    Post.objects.create(title="FeaturedPost", summary="s", body="x",
                        topic=topic, is_featured=True)
    Post.objects.create(title="RegularPost",  summary="s", body="x", topic=topic)
    r = client.get("/blog/")
    assert r.context["featured"].title == "FeaturedPost"
    # Featured post must NOT also appear in the rest grid
    rest_titles = [p.title for p in r.context["posts"]]
    assert "FeaturedPost" not in rest_titles
    assert "RegularPost" in rest_titles


def test_list_topic_chip_filters(client, topic):
    other = Topic.objects.create(name="Engineering")
    Post.objects.create(title="ProdPost", summary="s", body="x", topic=topic)
    Post.objects.create(title="EngPost",  summary="s", body="x", topic=other)
    r = client.get(f"/blog/?topic={topic.slug}")
    titles = [p.title for p in r.context["posts"]]
    assert "ProdPost" in titles
    assert "EngPost" not in titles


def test_list_search_matches_title_and_body(client, topic):
    Post.objects.create(title="StripeArticle", summary="s", body="webhook",
                        topic=topic)
    Post.objects.create(title="OtherArticle",  summary="s", body="something",
                        topic=topic)
    r = client.get("/blog/?q=stripe")
    titles = [p.title for p in r.context["posts"]]
    assert "StripeArticle" in titles
    assert "OtherArticle" not in titles


def test_list_search_skips_featured_hero(client, topic):
    """When the user is searching, featured shouldn't pin to the top."""
    Post.objects.create(title="FeaturedPost", summary="s", body="x",
                        topic=topic, is_featured=True)
    r = client.get("/blog/?q=Featured")
    assert r.context["featured"] is None  # search mode disables hero


# ── Detail ────────────────────────────────────────────────────────────

def test_detail_renders_paragraphs(client, topic):
    p = Post.objects.create(title="TheArticle", summary="hello",
                            body="Para one.\n\nPara two.", topic=topic)
    r = client.get(f"/blog/{p.slug}/")
    assert r.status_code == 200
    assert b"TheArticle" in r.content
    assert b"Para one." in r.content
    assert b"Para two." in r.content


def test_detail_increments_view_count(client, topic):
    p = Post.objects.create(title="ViewedPost", body="x", topic=topic, view_count=4)
    client.get(f"/blog/{p.slug}/")
    p.refresh_from_db()
    assert p.view_count == 5


def test_unpublished_detail_404s(client, topic):
    p = Post.objects.create(title="DraftPost", body="x", topic=topic,
                            is_published=False)
    r = client.get(f"/blog/{p.slug}/")
    assert r.status_code == 404


def test_detail_shows_related_in_same_topic(client, topic):
    main = Post.objects.create(title="MainPost",   body="x", topic=topic)
    Post.objects.create(title="SiblingPost", body="x", topic=topic)
    other = Topic.objects.create(name="Other")
    Post.objects.create(title="StrangerPost", body="x", topic=other)
    r = client.get(f"/blog/{main.slug}/")
    assert b"SiblingPost" in r.content
    assert b"StrangerPost" not in r.content


# ── Topic ─────────────────────────────────────────────────────────────

def test_topic_renders_post_list(client, topic):
    Post.objects.create(title="TopicPost", body="x", topic=topic)
    r = client.get(f"/blog/t/{topic.slug}/")
    assert r.status_code == 200
    assert b"TopicPost" in r.content


def test_topic_excludes_unpublished(client, topic):
    Post.objects.create(title="VisibleX", body="x", topic=topic, is_published=True)
    Post.objects.create(title="HiddenX",  body="x", topic=topic, is_published=False)
    r = client.get(f"/blog/t/{topic.slug}/")
    assert b"VisibleX" in r.content
    assert b"HiddenX" not in r.content


def test_unknown_topic_404s(client):
    r = client.get("/blog/t/nonexistent/")
    assert r.status_code == 404
