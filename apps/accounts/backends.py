"""Backend di autenticazione: login con username OPPURE email."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Permette di autenticarsi indifferentemente con username o email
    (email case-insensitive). Mantiene tutti i controlli di ModelBackend
    (is_active, permessi)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        User = get_user_model()
        user = None
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email__iexact=username)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                user = None
        if user is None:
            # Mitiga il timing attack hashando comunque una password.
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
