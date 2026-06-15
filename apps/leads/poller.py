"""In-process lead poller — speed-to-lead garantito.

Esegue la sync dalle sorgenti broker (IREV / TrackBox / Affinitrax / …)
ogni `LEAD_POLL_SECONDS` secondi, così ogni lead pullato compare nel CRM
entro l'intervallo configurato (default 30s) senza un worker esterno.

Avviato una sola volta da `apex/asgi.py` (solo se LEAD_POLLER=true), quindi
gira una volta per processo Daphne e mai durante migrate/collectstatic.

NB: i lead via postback e via landing sono già in tempo reale — il poller
copre solo le sorgenti che vanno interrogate (pull).
"""
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()

# Heartbeat condiviso col processo web (stesso processo Daphne) per
# mostrare "ultima sync" nella UI senza scrivere sul DB ogni 30s.
STATE = {
    "enabled": False,
    "interval": None,
    "last_run": None,       # datetime UTC dell'ultimo giro
    "last_ok": 0,
    "last_errors": 0,
    "consecutive_failures": 0,
}


def get_heartbeat() -> dict:
    return dict(STATE)


def _truthy(value: str) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _loop(interval: int) -> None:
    from django.db import close_old_connections
    from django.utils import timezone

    from apps.leads.models import SyncAudit
    from apps.leads.sync import run_all_sources

    logger.info("Lead poller avviato (intervallo %ss)", interval)
    while True:
        try:
            close_old_connections()
            ok, errors = run_all_sources()
            STATE["last_run"] = timezone.now()
            STATE["last_ok"] = len(ok)
            STATE["last_errors"] = len(errors)
            STATE["consecutive_failures"] = 0
            # Scrivi un audit solo quando c'è stata attività reale,
            # per non gonfiare la tabella con righe vuote ogni 30s.
            if ok or errors:
                SyncAudit.objects.create(
                    action="sync" if not errors else "error",
                    source="poller",
                    details=("\n".join(
                        ([f"ok: {', '.join(ok)}"] if ok else [])
                        + ([f"errors: {', '.join(errors)}"] if errors else [])
                    )),
                )
                logger.info("Poller sync: %d ok, %d errori", len(ok), len(errors))
        except Exception:
            STATE["consecutive_failures"] += 1
            logger.exception("Poller sync fallito (fallimenti consecutivi: %d)",
                             STATE["consecutive_failures"])
            # Backoff esponenziale sugli errori ripetuti, max 5x l'intervallo,
            # così non martelliamo un'API broker che è temporaneamente down.
            backoff = min(interval * STATE["consecutive_failures"], interval * 5)
            close_old_connections()
            time.sleep(backoff)
            continue
        finally:
            close_old_connections()
        time.sleep(interval)


def start_poller() -> None:
    """Avvia il thread daemon del poller, una sola volta."""
    global _started
    with _lock:
        if _started:
            return
        if not _truthy(os.environ.get("LEAD_POLLER", "")):
            logger.info("Lead poller disattivato (LEAD_POLLER non impostato).")
            return
        try:
            interval = int(os.environ.get("LEAD_POLL_SECONDS", "30"))
        except ValueError:
            interval = 30
        interval = max(5, interval)
        STATE["enabled"] = True
        STATE["interval"] = interval
        thread = threading.Thread(
            target=_loop, args=(interval,), daemon=True, name="lead-poller")
        thread.start()
        _started = True
