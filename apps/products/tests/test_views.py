import pytest

from apps.accounts.tests.factories import UserFactory

from .factories import ProductFactory


@pytest.mark.django_db
def test_product_list_requires_login(client):
    response = client.get("/products/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_product_list_renders_rows(client):
    client.force_login(UserFactory())
    ProductFactory.create_batch(3)
    response = client.get("/products/")
    assert response.status_code == 200
    # Each product row shows its SKU
    assert response.content.count(b"SKU-") >= 3


@pytest.mark.django_db
def test_product_list_paginates(client):
    client.force_login(UserFactory())
    # Products TableView page_size is 25 — create 30 to trigger pagination.
    ProductFactory.create_batch(30)
    response = client.get("/products/")
    assert response.context["page_obj"].paginator.count == 30
    assert len(response.context["page_obj"].object_list) == 25


@pytest.mark.django_db
def test_product_list_empty_state(client):
    client.force_login(UserFactory())
    response = client.get("/products/")
    assert b"No products yet" in response.content


@pytest.mark.django_db
def test_product_detail_renders(client):
    client.force_login(UserFactory())
    p = ProductFactory()
    response = client.get(f"/products/{p.pk}/")
    assert response.status_code == 200
    assert p.name.encode() in response.content
    assert p.sku.encode() in response.content


@pytest.mark.django_db
def test_product_detail_requires_login(client):
    p = ProductFactory()
    response = client.get(f"/products/{p.pk}/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_product_create_get_renders_form(client):
    from apps.products.tests.factories import CategoryFactory
    client.force_login(UserFactory())
    CategoryFactory()  # ensure at least one category for the select
    response = client.get("/products/new/")
    assert response.status_code == 200
    assert b"name=\"name\"" in response.content


@pytest.mark.django_db
def test_product_create_post_persists(client):
    from apps.products.tests.factories import CategoryFactory
    client.force_login(UserFactory())
    cat = CategoryFactory()
    response = client.post("/products/new/", {
        "name": "Fresh",
        "slug": "fresh",
        "sku": "FR-1",
        "price": "9.99",
        "stock": "5",
        "status": "draft",
        "category": cat.pk,
        "description": "",
    })
    assert response.status_code == 302
    from apps.products.models import Product
    assert Product.objects.filter(slug="fresh").exists()


@pytest.mark.django_db
def test_product_edit_updates_fields(client):
    client.force_login(UserFactory())
    p = ProductFactory()
    response = client.post(f"/products/{p.pk}/edit/", {
        "name": "Updated Name",
        "slug": p.slug,
        "sku": p.sku,
        "price": str(p.price),
        "stock": p.stock,
        "status": p.status,
        "category": p.category.pk,
        "description": "Edited description",
    })
    assert response.status_code == 302
    p.refresh_from_db()
    assert p.name == "Updated Name"
    assert p.description == "Edited description"


@pytest.mark.django_db
def test_product_create_requires_login(client):
    response = client.get("/products/new/")
    assert response.status_code == 302
