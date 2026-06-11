import pytest

from apps.help.models import Article, Category

pytestmark = pytest.mark.django_db


def test_category_slug_auto_generated():
    c = Category.objects.create(name="Getting Started")
    assert c.slug == "getting-started"


def test_category_slug_collision_handled():
    Category.objects.create(name="Account")
    c = Category.objects.create(name="Account")
    assert c.slug == "account-2"


def test_article_slug_auto_generated():
    c = Category.objects.create(name="X")
    a = Article.objects.create(category=c, title="My First Article", body="Hello")
    assert a.slug == "my-first-article"


def test_article_paragraphs_split_on_blank_lines():
    c = Category.objects.create(name="X")
    a = Article.objects.create(category=c, title="A",
        body="First paragraph.\n\nSecond paragraph here.\n\nThird.")
    assert a.paragraphs == ["First paragraph.", "Second paragraph here.", "Third."]


def test_paragraphs_skips_empty_blocks():
    c = Category.objects.create(name="X")
    a = Article.objects.create(category=c, title="A",
        body="\n\n\nReal content.\n\n   \n\nMore.")
    assert a.paragraphs == ["Real content.", "More."]


def test_reading_minutes_at_least_one():
    c = Category.objects.create(name="X")
    a = Article.objects.create(category=c, title="Tiny", body="hi")
    assert a.reading_minutes == 1


def test_reading_minutes_scales_with_word_count():
    c = Category.objects.create(name="X")
    body = " ".join(["word"] * 600)  # ~3 minutes at 200wpm
    a = Article.objects.create(category=c, title="Long", body=body)
    assert a.reading_minutes == 3


def test_increment_views_uses_F_to_avoid_race():
    c = Category.objects.create(name="X")
    a = Article.objects.create(category=c, title="A", body="hi", view_count=10)
    a.increment_views()
    a.refresh_from_db()
    assert a.view_count == 11


def test_category_article_count_excludes_unpublished():
    c = Category.objects.create(name="X")
    Article.objects.create(category=c, title="Published", body="x", is_published=True)
    Article.objects.create(category=c, title="Draft",     body="x", is_published=False)
    assert c.article_count == 1
