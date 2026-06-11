import pytest

from apps.help.models import Article, Category

pytestmark = pytest.mark.django_db


@pytest.fixture
def cat():
    return Category.objects.create(
        name="Getting started", icon="rocket", accent="#16a34a", position=1,
    )


# ── Home ──────────────────────────────────────────────────────────────

def test_home_renders_for_anon(client):
    r = client.get("/help/")
    assert r.status_code == 200
    assert b"How can we help" in r.content


def test_home_lists_featured_and_categories(client, cat):
    Article.objects.create(category=cat, title="Featured Pick",
                           summary="bla", body="x", is_featured=True)
    Article.objects.create(category=cat, title="Other Article",
                           summary="bla", body="x", view_count=999)
    r = client.get("/help/")
    assert b"Featured Pick" in r.content
    assert b"Getting started" in r.content


def test_home_hides_categories_without_published_articles(client):
    Category.objects.create(name="EmptyCat", icon="package")
    r = client.get("/help/")
    assert b"EmptyCat" not in r.content


# ── Category ──────────────────────────────────────────────────────────

def test_category_renders(client, cat):
    Article.objects.create(category=cat, title="One", body="a")
    Article.objects.create(category=cat, title="Two", body="b")
    r = client.get(f"/help/c/{cat.slug}/")
    assert r.status_code == 200
    assert b"One" in r.content
    assert b"Two" in r.content


def test_category_excludes_unpublished_articles(client, cat):
    Article.objects.create(category=cat, title="Visible",   body="a", is_published=True)
    Article.objects.create(category=cat, title="Invisible", body="b", is_published=False)
    r = client.get(f"/help/c/{cat.slug}/")
    assert b"Visible" in r.content
    assert b"Invisible" not in r.content


def test_unknown_category_404s(client):
    r = client.get("/help/c/nonexistent/")
    assert r.status_code == 404


# ── Article ───────────────────────────────────────────────────────────

def test_article_renders_body_paragraphs(client, cat):
    a = Article.objects.create(category=cat, title="Title",
        summary="Summary line",
        body="Para one.\n\nPara two has more text.")
    r = client.get(f"/help/a/{a.slug}/")
    assert r.status_code == 200
    assert b"Para one." in r.content
    assert b"Para two" in r.content


def test_article_view_increments_count(client, cat):
    a = Article.objects.create(category=cat, title="Counter", body="x", view_count=5)
    client.get(f"/help/a/{a.slug}/")
    a.refresh_from_db()
    assert a.view_count == 6


def test_unpublished_article_404s(client, cat):
    a = Article.objects.create(category=cat, title="Hidden", body="x", is_published=False)
    r = client.get(f"/help/a/{a.slug}/")
    assert r.status_code == 404


def test_article_shows_related_in_same_category(client, cat):
    main = Article.objects.create(category=cat, title="Main", body="x")
    Article.objects.create(category=cat, title="Sibling", body="y")
    other_cat = Category.objects.create(name="Other")
    Article.objects.create(category=other_cat, title="Stranger", body="z")
    r = client.get(f"/help/a/{main.slug}/")
    assert b"Sibling" in r.content
    assert b"Stranger" not in r.content


# ── Search ────────────────────────────────────────────────────────────

def test_search_matches_title(client, cat):
    Article.objects.create(category=cat, title="How to invite teammates", body="x")
    Article.objects.create(category=cat, title="Reading invoices",        body="x")
    r = client.get("/help/search/?q=invite")
    assert b"How to invite teammates" in r.content
    assert b"Reading invoices" not in r.content


def test_search_matches_body(client, cat):
    Article.objects.create(category=cat, title="WebhookArticle", body="webhook signatures via HMAC")
    Article.objects.create(category=cat, title="UnrelatedArticle", body="rate limits and retries")
    r = client.get("/help/search/?q=webhook")
    assert b"WebhookArticle" in r.content
    assert b"UnrelatedArticle" not in r.content


def test_search_excludes_unpublished(client, cat):
    Article.objects.create(category=cat, title="Public",  body="match", is_published=True)
    Article.objects.create(category=cat, title="Private", body="match", is_published=False)
    r = client.get("/help/search/?q=match")
    assert b"Public" in r.content
    assert b"Private" not in r.content


def test_empty_search_shows_prompt(client):
    r = client.get("/help/search/?q=")
    assert r.status_code == 200
    assert b"Enter a search term" in r.content


def test_search_no_results_empty_state(client, cat):
    Article.objects.create(category=cat, title="Real", body="content")
    r = client.get("/help/search/?q=zzznomatchzzz")
    assert b"No results" in r.content


def test_home_query_redirects_into_search(client, cat):
    Article.objects.create(category=cat, title="Searchable", body="x")
    r = client.get("/help/?q=Searchable")
    # home view delegates to search; we render search.html on the same URL
    assert b"Searchable" in r.content
    assert b"result" in r.content.lower()
