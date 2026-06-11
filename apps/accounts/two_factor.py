"""TwoFactorDevice model and helpers.

Kept in its own module (rather than models.py) to keep the model file focused
on the User model. Django picks it up because models.py will import it."""

import hashlib
import secrets

import pyotp
from django.conf import settings
from django.db import models
from django.utils import timezone

# Unambiguous alphabet — excludes O, 0, I, 1.
_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _random_recovery_code() -> str:
    """Format: XXXXX-XXXXX (10 chars + a dash for readability)."""
    left = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(5))
    right = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(5))
    return f"{left}-{right}"


def _hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.upper().encode()).hexdigest()


class TwoFactorDevice(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor",
    )
    secret = models.CharField(max_length=32)
    confirmed = models.BooleanField(default=False)
    recovery_codes = models.JSONField(default=list)
    # Shape: [{"hash": "<sha256>", "used_at": null | ISO-8601-string}, ...]
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "accounts"

    def __str__(self) -> str:
        status = "on" if self.confirmed else "setup"
        return f"2FA for {self.user.username} ({status})"

    def provisioning_uri(self, issuer: str = "Apex Dashboard") -> str:
        return pyotp.totp.TOTP(self.secret).provisioning_uri(
            name=self.user.username, issuer_name=issuer
        )

    def verify_totp(self, code: str, valid_window: int = 1) -> bool:
        if not code:
            return False
        return pyotp.TOTP(self.secret).verify(code.strip(), valid_window=valid_window)

    def verify_recovery_code(self, code: str) -> bool:
        if not code:
            return False
        target = _hash_recovery_code(code.strip())
        for entry in self.recovery_codes:
            if entry.get("hash") == target and entry.get("used_at") is None:
                entry["used_at"] = timezone.now().isoformat()
                self.save(update_fields=["recovery_codes"])
                return True
        return False

    def generate_recovery_codes(self, count: int = 8) -> list[str]:
        """Replaces existing codes. Returns plaintext — the caller MUST display them."""
        plaintext = [_random_recovery_code() for _ in range(count)]
        self.recovery_codes = [
            {"hash": _hash_recovery_code(c), "used_at": None} for c in plaintext
        ]
        self.save(update_fields=["recovery_codes"])
        return plaintext

    @classmethod
    def create_unconfirmed(cls, user) -> "TwoFactorDevice":
        cls.objects.filter(user=user).delete()
        return cls.objects.create(
            user=user, secret=pyotp.random_base32(), confirmed=False
        )
