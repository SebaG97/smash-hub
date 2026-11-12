"""The API's background loop that keeps the local start.gg copy fresh (ADR-022).

It runs inside the API process (no worker, queue or extra component): a daemon thread
wakes every STARTGG_SYNC_TICK_SECONDS and runs service.tick. Several API instances may
each run one; the database gate in service.claim lets only one sync work at a time.
"""

import logging
import threading

from app.sync import service

log = logging.getLogger(__name__)
FIRST_DELAY = 20  # let the API finish starting before the first start.gg request


class Scheduler:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True, name="startgg-sync")

    def start(self):
        log.info("start.gg sync scheduler on (every %ss)", self.settings.startgg_sync_tick_seconds)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        # A sync in progress finishes its current request; the thread is a daemon anyway.
        self.thread.join(timeout=5)

    def loop(self):
        delay = min(FIRST_DELAY, self.settings.startgg_sync_tick_seconds)
        while not self.stopping.wait(delay):
            try:
                service.tick(self.engine, self.settings, self.stopping)
            except Exception:
                log.exception("start.gg sync tick failed")
            delay = self.settings.startgg_sync_tick_seconds


def maybe_start(engine, settings):
    """A running Scheduler when STARTGG_SYNC_ENABLED and a token are set, else None."""
    token = settings.startgg_api_token
    if not settings.startgg_sync_enabled:
        return None
    if token is None or not token.get_secret_value().strip():
        log.warning("STARTGG_SYNC_ENABLED without STARTGG_API_TOKEN: sync stays off")
        return None
    scheduler = Scheduler(engine, settings)
    scheduler.start()
    return scheduler
