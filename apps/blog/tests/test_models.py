import pytest

from apps.blog.models import Post, Topic

pytestmark = pytest.mark.django_db


def test_topic_slug_auto_generated():
    t = Topic.objects.create(name="Engineering Notes")
    assert t.slug == "engineering-notes"


def test_topic_slug_collision_handled():
    Topic.objects.create(name="Product")
    t = Topic.objects.create(name="Product")
    assert t.slug == "product-2"


def test_post_slug_auto_generated():
    p = Post.objects.create(title="Hello World", body="x")
    assert p.slug == "hello-world"


def test_post_paragraphs_split_on_blank_lines():
    p = Post.objects.create(title="X",
        body="One.\n\nTwo paragraphs.\n\nThree.")
    assert p.paragraphs == ["One.", "Two paragraphs.", "Three."]


def test_reading_minutes_at_least_one():
    p = Post.objects.create(title="Tiny", body="hi")
    assert p.reading_minutes == 1


def test_reading_minutes_scales():
    body = " ".join(["word"] * 600)
    p = Post.objects.create(title="Long", body=body)
    assert p.reading_minutes == 3


def test_increment_views_uses_F():
    p = Post.objects.create(title="X", body="x", view_count=10)
    p.increment_views()
    p.refresh_from_db()
    assert p.view_count == 11


def test_topic_post_count_excludes_unpublished():
    t = Topic.objects.create(name="X")
    Post.objects.create(title="Pub",  body="x", topic=t, is_published=True)
    Post.objects.create(title="Draft", body="x", topic=t, is_published=False)
    assert t.post_count == 1
