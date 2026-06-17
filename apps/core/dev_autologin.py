"""Auto-login SOLO per lo sviluppo locale (mai in produzione).

Attivo unicamente quando `settings.DEV_AUTOLOGIN` è True — flag impostato
solo in `apex/settings/dev.py`. In `prod.py` non esiste, quindi questo
middleware non viene nemmeno caricato sul server live.

Scopo: aprire il sito in locale (http://localhost:8000) ed entrare senza
inserire alcuna password. Se l'utente locale non è loggato, lo autentica
come superuser `admin`, creandolo al volo se non esiste.
"""
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.utils import timezone

_BACKEND = "django.contrib.auth.backends.ModelBackend"


class DevAutoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "DEV_AUTOLOGIN", False) and not request.user.is_authenticated:
            User = get_user_model()
            user = User.objects.filter(username="admin").first()
            if user is None:
                user = User.objects.create_superuser(
                    username="admin", email="admin@local", password="admin")
            # Assicura che l'utente sia pienamente utilizzabile (staff,
            # superuser, attivo, email verificata) per non incappare in
            # redirect di verifica/permessi.
            changed = False
            for attr, val in (("is_staff", True), ("is_superuser", True),
                              ("is_active", True)):
                if getattr(user, attr) != val:
                    setattr(user, attr, val)
                    changed = True
            if hasattr(user, "email_verified_at") and not user.email_verified_at:
                user.email_verified_at = timezone.now()
                changed = True
            if changed:
                user.save()
            login(request, user, backend=_BACKEND)
            request.user = user
        return self.get_response(request)
