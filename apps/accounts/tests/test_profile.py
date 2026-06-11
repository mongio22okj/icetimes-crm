import pytest

from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_profile_requires_login(client):
    response = client.get("/settings/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_profile_get_renders_form_with_user_data(client):
    user = UserFactory(first_name="Alice", last_name="Chen")
    client.force_login(user)
    response = client.get("/settings/profile/")
    assert response.status_code == 200
    assert b"Alice" in response.content
    assert user.email.encode() in response.content


@pytest.mark.django_db
def test_profile_post_updates_fields(client):
    user = UserFactory(first_name="Original", bio="")
    client.force_login(user)
    response = client.post("/settings/profile/", {
        "first_name": "Updated",
        "last_name": user.last_name,
        "email": user.email,
        "bio": "My new bio",
    })
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.first_name == "Updated"
    assert user.bio == "My new bio"


@pytest.mark.django_db
def test_profile_does_not_allow_username_change(client):
    """Username is a read-only identifier — users can't change it via profile."""
    user = UserFactory(username="original_name")
    client.force_login(user)
    client.post("/settings/profile/", {
        "username": "hacked_name",
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "bio": "",
    })
    user.refresh_from_db()
    assert user.username == "original_name"


@pytest.mark.django_db
def test_profile_edit_updates_only_own_profile(client):
    user_a = UserFactory(username="user_a")
    user_b = UserFactory(username="user_b", first_name="B")
    client.force_login(user_a)
    # user_a POSTs — should edit user_a, not user_b
    response = client.post("/settings/profile/", {
        "first_name": "AliceNew",
        "last_name": user_a.last_name,
        "email": user_a.email,
        "bio": "",
    })
    user_a.refresh_from_db()
    user_b.refresh_from_db()
    assert user_a.first_name == "AliceNew"
    assert user_b.first_name == "B"  # Unchanged


@pytest.mark.django_db
def test_settings_root_redirects_to_profile(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/settings/")
    assert response.status_code == 302
    assert response["Location"].endswith("/settings/profile/")


@pytest.mark.django_db
def test_placeholder_tabs_render_200(client):
    user = UserFactory()
    client.force_login(user)
    for slug in ("password", "appearance", "two-factor"):
        response = client.get(f"/settings/{slug}/")
        assert response.status_code == 200, f"{slug} returned {response.status_code}"


@pytest.mark.django_db
def test_settings_layout_marks_active_tab(client):
    """The Profile tab link should carry the active-state classes when we're
    on /settings/profile/."""
    user = UserFactory()
    client.force_login(user)
    response = client.get("/settings/profile/")
    html = response.content.decode()
    # Find the Profile link specifically — should include the active classes
    import re
    profile_link = re.search(r'<a href="/settings/profile/"[^>]*>Profile</a>', html)
    assert profile_link, "Profile link not found in rendered HTML"
    assert "bg-accent" in profile_link.group(0), "Profile tab should be active"
