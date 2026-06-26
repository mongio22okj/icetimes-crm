"""Custom static files storage."""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class NonStrictManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Manifest static storage che NON va in 500 su voci mancanti.

    Il template referenzia icone favicon/PWA (`icons/*.png`) che sono
    placeholder di branding da fornire dal compratore. Senza quei file, il
    manifest strict solleva un errore su OGNI pagina che carica base.html.
    Non-strict = fallback al path non-hashato invece dell'eccezione.
    """
    manifest_strict = False
