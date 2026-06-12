"""Compute a 0-100 quality score for a Lead based on data completeness.

Used at postback time to surface high-quality leads first in the CRM
(filter by score, sort by score desc). Catches obvious junk like missing
email/phone or country mismatch without needing third-party enrichment.
"""
import re


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_E164_PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_COUNTRY_RE = re.compile(r"^[A-Za-z]{2}$")


def compute_score(lead) -> int:
    """Return a quality score 0-100 for `lead`."""
    score = 0

    # Email — both required and well-formed.
    if lead.email and _EMAIL_RE.match(lead.email):
        score += 25
    elif lead.email:
        score += 8

    # Phone — E.164 international format ideal.
    phone = (lead.phone or "").strip()
    if phone and _E164_PHONE_RE.match(phone):
        score += 25
    elif phone and len(phone) >= 7:
        score += 10

    # Full name.
    if lead.firstname and lead.lastname:
        score += 20
    elif lead.firstname or lead.lastname:
        score += 8

    # Country.
    country = (lead.country or "").strip()
    if country and _COUNTRY_RE.match(country):
        score += 10

    # Status.
    if lead.is_deposit:
        score += 15
    elif lead.status:
        score += 5

    # Source attribution.
    if lead.source and lead.source not in ("postback", ""):
        score += 5

    return min(100, score)
