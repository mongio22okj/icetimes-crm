import os


def get_external_leads_endpoint():
    return os.environ.get("EXTERNAL_LEADS_ENDPOINT", "")


def get_api_headers():
    token = os.environ.get("EXTERNAL_LEADS_TOKEN", "")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
