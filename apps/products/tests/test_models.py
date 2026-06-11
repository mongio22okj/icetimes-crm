import pytest

from apps.products.models import Category, Product


@pytest.mark.django_db
def test_category_requires_name_and_slug():
    cat = Category.objects.create(name="Electronics", slug="electronics")
    assert str(cat) == "Electronics"


@pytest.mark.django_db
def test_product_has_required_fields():
    cat = Category.objects.create(name="X", slug="x")
    p = Product.objects.create(
        name="Widget", slug="widget", sku="SKU-001",
        price=19.99, stock=50, category=cat,
    )
    assert p.name == "Widget"
    assert str(p) == "Widget"


@pytest.mark.django_db
def test_product_status_defaults_to_draft():
    cat = Category.objects.create(name="X", slug="x")
    p = Product.objects.create(
        name="Y", slug="y", sku="Z", price=1, stock=1, category=cat,
    )
    assert p.status == "draft"


@pytest.mark.django_db
def test_product_orders_by_newest_created():
    cat = Category.objects.create(name="X", slug="x")
    p1 = Product.objects.create(name="Old", slug="old", sku="O-1", price=1, stock=1, category=cat)
    p2 = Product.objects.create(name="New", slug="new", sku="N-1", price=1, stock=1, category=cat)
    assert list(Product.objects.all()) == [p2, p1]
