"""E2E coverage for Phase 6c Files."""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_browser_shows_seeded_contents(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/files/")
    page.locator("table").wait_for(state="visible", timeout=5000)
    # Documents folder seeded
    page.locator("text=Documents").first.wait_for(state="visible", timeout=5000)


def test_create_folder_flow(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/files/folder/new/")
    page.fill("input[name='name']", "E2E Test Folder")
    page.click("button:has-text('Create folder')")
    page.wait_for_url(f"{server_url}/files/")
    page.locator("text=E2E Test Folder").first.wait_for(state="visible", timeout=5000)


def test_upload_file_flow(page, server_url, tmp_path):
    # Create a small temp file to upload
    fp = tmp_path / "e2e_upload.txt"
    fp.write_text("Hello from playwright!")

    _login(page, server_url)
    page.goto(f"{server_url}/files/upload/")
    page.set_input_files("input[name='files']", str(fp))
    page.click("button:has-text('Upload')")
    page.wait_for_url(f"{server_url}/files/")
    page.locator("text=e2e_upload.txt").first.wait_for(state="visible", timeout=5000)
