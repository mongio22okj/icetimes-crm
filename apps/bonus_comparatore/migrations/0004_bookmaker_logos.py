"""Imposta logo_url dei bookmaker usando il servizio favicon pubblico.

I favicon (Google s2, 128px) sono icone pubbliche e sempre raggiungibili,
usate come segnaposto-logo finché non si caricano i loghi ufficiali via admin.
Nei template vengono mostrati come icona accanto al nome del brand.
Non sovrascrive un logo già impostato a mano (file o URL non-favicon).
"""
from urllib.parse import urlparse

from django.db import migrations


def _favicon(url):
    host = urlparse(url).netloc or ""
    host = host.lstrip("www.") if host.startswith("www.") else host
    if not host:
        return ""
    return f"https://www.google.com/s2/favicons?domain={host}&sz=128"


def set_logos(apps, schema_editor):
    Bookmaker = apps.get_model("bonus_comparatore", "Bookmaker")
    for bm in Bookmaker.objects.all():
        # Non toccare loghi già caricati come file o URL personalizzato.
        if bm.logo:
            continue
        if bm.logo_url and "s2/favicons" not in bm.logo_url:
            continue
        fav = _favicon(bm.official_url)
        if fav:
            bm.logo_url = fav
            bm.save(update_fields=["logo_url"])


def clear_logos(apps, schema_editor):
    Bookmaker = apps.get_model("bonus_comparatore", "Bookmaker")
    for bm in Bookmaker.objects.all():
        if bm.logo_url and "s2/favicons" in bm.logo_url:
            bm.logo_url = ""
            bm.save(update_fields=["logo_url"])


class Migration(migrations.Migration):
    dependencies = [
        ("bonus_comparatore", "0003_clicklog"),
    ]

    operations = [
        migrations.RunPython(set_logos, clear_logos),
    ]
