"""Worker de collecte planifiée.

Boucle : toutes les DDW_WORKER_POLL_S secondes, réserve les sources dues (SKIP LOCKED,
priorité puis ancienneté) et les collecte en parallèle borné. Chaque source est isolée :
une source défaillante n'affecte pas les autres (backoff exponentiel, circuit ouvert après 5 échecs).

Lancement : python -m app.worker   (ou --once pour un passage unique)
"""

from __future__ import annotations

import argparse
import logging
import signal
import time
from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings
from app.db import session_scope
from app.logging_config import configure_logging
from app.services.ingest import claim_due_sources, run_source

log = logging.getLogger("ddw.worker")
_stop = False


def _handle_stop(*_: object) -> None:
    global _stop
    _stop = True
    log.info("Arrêt demandé, fin du cycle en cours")


def collect_one(source_id: int) -> str:
    with session_scope() as session:
        run = run_source(session, source_id)
        log.info(
            "Source %s : %s (%s nouveaux, %s doublons, %s ms)",
            source_id, run.status, run.docs_created, run.duplicates, run.duration_ms,
        )
        return run.status


def cycle(pool: ThreadPoolExecutor, concurrency: int) -> int:
    with session_scope() as session:
        ids = claim_due_sources(session, limit=concurrency * 4)
    if ids:
        list(pool.map(collect_one, ids))
    return len(ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker de collecte Defense Drone Watch")
    parser.add_argument("--once", action="store_true", help="un seul passage puis sortie")
    args = parser.parse_args()
    configure_logging()
    settings = get_settings()
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    log.info("Worker démarré (concurrence=%s, intervalle=%ss)", settings.worker_concurrency, settings.worker_poll_s)
    with ThreadPoolExecutor(max_workers=settings.worker_concurrency) as pool:
        while not _stop:
            try:
                n = cycle(pool, settings.worker_concurrency)
                if n:
                    log.info("Cycle terminé : %s source(s) collectée(s)", n)
            except Exception:
                log.exception("Cycle de collecte en échec")
            if args.once:
                break
            for _ in range(settings.worker_poll_s):
                if _stop:
                    break
                time.sleep(1)


if __name__ == "__main__":
    main()
