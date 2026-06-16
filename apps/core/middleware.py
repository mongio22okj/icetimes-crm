"""Site-wide access gate (HTTP Basic Auth).

Blinda l'intero sito dietro una password del browser, lasciando aperti
solo gli endpoint pubblici necessari al flusso lead (landing dei broker,
link di tracciamento, postback, API track, health check, asset PWA).

Attivazione: bastano le env var SITE_GATE_USER e SITE_GATE_PASSWORD.
Se non sono impostate, il gate è disattivato (sito normale).
"""
import base64
import hmac

from django.conf import settings
from django.http import HttpResponse


class SiteGateMiddleware:
    """Richiede Basic Auth per ogni path non esente."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.user = getattr(settings, "SITE_GATE_USER", "") or ""
        self.password = getattr(settings, "SITE_GATE_PASSWORD", "") or ""
        self.exempt = tuple(getattr(settings, "SITE_GATE_EXEMPT_PREFIXES", ()))
        self.realm = getattr(settings, "SITE_GATE_REALM", "IceTimes")

    @property
    def enabled(self) -> bool:
        return bool(self.user and self.password)

    def __call__(self, request):
        if not self.enabled or self._is_exempt(request.path) or self._ok(request):
            return self.get_response(request)
        return self._challenge()

    def _is_exempt(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.exempt)

    def _ok(self, request) -> bool:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header[6:]).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        user, _, pw = decoded.partition(":")
        # compare_digest su entrambi per evitare timing leak.
        return (hmac.compare_digest(user, self.user)
                and hmac.compare_digest(pw, self.password))

    def _challenge(self) -> HttpResponse:
        resp = HttpResponse("Accesso riservato.", status=401,
                            content_type="text/plain; charset=utf-8")
        resp["WWW-Authenticate"] = f'Basic realm="{self.realm}"'
        return resp
