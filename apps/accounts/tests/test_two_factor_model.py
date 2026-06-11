import hashlib

import pyotp
import pytest

from apps.accounts.tests.factories import UserFactory
from apps.accounts.two_factor import TwoFactorDevice

pytestmark = pytest.mark.django_db


def test_create_unconfirmed_creates_fresh_device():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    assert d.user_id == user.id
    assert d.confirmed is False
    assert len(d.secret) == 32


def test_create_unconfirmed_replaces_existing_device():
    user = UserFactory()
    first = TwoFactorDevice.create_unconfirmed(user)
    second = TwoFactorDevice.create_unconfirmed(user)
    assert second.pk != first.pk
    assert TwoFactorDevice.objects.filter(user=user).count() == 1


def test_provisioning_uri_is_valid_otpauth():
    user = UserFactory(username="alice")
    d = TwoFactorDevice.create_unconfirmed(user)
    uri = d.provisioning_uri()
    assert uri.startswith("otpauth://totp/")
    assert "alice" in uri
    assert "Apex%20Dashboard" in uri or "Apex+Dashboard" in uri


def test_verify_totp_accepts_current_window():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    current_code = pyotp.TOTP(d.secret).now()
    assert d.verify_totp(current_code)


def test_verify_totp_rejects_wrong_code():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    assert not d.verify_totp("000000")


def test_generate_recovery_codes_returns_plaintext_stores_hashes():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    codes = d.generate_recovery_codes(count=8)
    assert len(codes) == 8
    for c in codes:
        assert "-" in c and len(c) == 11
    d.refresh_from_db()
    assert len(d.recovery_codes) == 8
    for entry in d.recovery_codes:
        assert entry["used_at"] is None
        assert len(entry["hash"]) == 64
    stored_hashes = {e["hash"] for e in d.recovery_codes}
    plain_as_hash = {hashlib.sha256(c.upper().encode()).hexdigest() for c in codes}
    assert stored_hashes == plain_as_hash


def test_verify_recovery_code_marks_used_first_time():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    codes = d.generate_recovery_codes()
    code = codes[0]
    assert d.verify_recovery_code(code)
    d.refresh_from_db()
    assert not d.verify_recovery_code(code)


def test_verify_recovery_code_case_insensitive():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    codes = d.generate_recovery_codes()
    assert d.verify_recovery_code(codes[0].lower())


def test_verify_recovery_code_rejects_unknown():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    d.generate_recovery_codes()
    assert not d.verify_recovery_code("XXXXX-XXXXX")
