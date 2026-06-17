# Backup landing IREV — "Immediate Edge 3.0"

Snapshot versionato della landing del broker **IREV** (`LeadSource` id 16, `kind=irev`).
Questi file sono un **backup**: la versione *viva* sta altrove (vedi sotto). Tenuti in `backups/`
perché gli asset statici/landing del progetto sono volutamente esclusi da git (`.gitignore`:
`static/*`, `staticfiles/`) e il contenuto landing vive in DB + server.

## File
- `landing_custom_html.html` — contenuto del campo `LeadSource(16).landing_custom_html`,
  servito da `BrokerLandingView` su **https://icetimes.it/b/irev/**. Clone della pagina
  "Immediate Edge 3.0", form dirottato sul nostro endpoint `/b/irev/submit/` → push a IREV.
  Restyle tema **navy+viola** (CSS lefroi di design rimossi, sostituiti da `icetimes-theme.css`),
  testi **interamente in italiano**.
- `icetimes-theme.css` — foglio di stile del tema CRM applicato alla landing. In produzione
  vive in `staticfiles/landings/irev/icetimes-theme.css` (servito da nginx, linkato come
  `icetimes-theme.css?v=N` nell'HTML).

## Dove sta il "vivo" (sorgente di verità)
- HTML: **DB di produzione**, `LeadSource(id=16).landing_custom_html`.
- CSS + altri asset (immagini, intlTelInput, integration.css, flag-icon…):
  server in `/opt/icetimes/staticfiles/landings/irev/`.
- Backup autorevole sul server: `/root/icetimes-backups/landings/irev/`.

## Ripristino
1. CSS: ricaricare `icetimes-theme.css` in `staticfiles/landings/irev/` e **bumpare `?v=N`**
   nell'HTML (Cloudflare cacha gli static 30 giorni — serve cambiare l'URL per bustare).
2. HTML: riscrivere il campo DB:
   ```python
   from apps.leads.models import LeadSource
   ls = LeadSource.objects.get(id=16)
   ls.landing_custom_html = open("landing_custom_html.html", encoding="utf-8").read()
   ls.save(update_fields=["landing_custom_html"])
   ```
