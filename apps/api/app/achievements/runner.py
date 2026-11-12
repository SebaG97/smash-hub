"""Background evaluation of achievements (SH-ACH-01).

Imports, organizer flags, ranking publications, Prode settlements and account links mark
achievements as dirty. With ACHIEVEMENTS_AUTO, a daemon thread evaluates shortly after
(coalescing bursts) and every ACHIEVEMENTS_INTERVAL_SECONDS as a safety net. Pages never
evaluate. An administrator can always start a run by hand.
"""

import logging
import threading
import time

from app.achievements import service

log = logging.getLogger(__name__)
TICK_SECONDS = 60
_state = {"dirty": None, "busy": False}
_lock = threading.Lock()


def mark_dirty(reason):
    with _lock:
        _state["dirty"] = _state["dirty"] or reason


def _take():
    with _lock:
        reason, _state["dirty"] = _state["dirty"], None
        return reason


def _run(engine, trigger, actor):
    with _lock:
        if _state["busy"]:
            return None
        _state["busy"] = True
    try:
        return service.run(engine, trigger=trigger, actor=actor)
    except Exception:
        log.exception("Achievement run failed")
        return None
    finally:
        with _lock:
            _state["busy"] = False


def start(engine, trigger, actor):
    """Start a run in a thread; returns False when one is already going on."""
    with _lock:
        if _state["busy"]:
            return False
    threading.Thread(
        target=_run, args=(engine, trigger, actor), daemon=True, name="achievements-run"
    ).start()
    return True


class Scheduler:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True, name="achievements")
        self.last = 0.0

    def loop(self):
        # A first run shortly after start-up, then on demand and on the interval.
        wait = 30
        while not self.stop_event.wait(wait):
            wait = TICK_SECONDS
            reason = _take()
            interval = self.settings.achievements_interval_seconds
            if reason or not self.last or time.monotonic() - self.last >= interval:
                _run(self.engine, reason or "schedule", "sistema")
                self.last = time.monotonic()

    def stop(self):
        self.stop_event.set()


def maybe_start(engine, settings):
    if not settings.achievements_auto:
        return None
    scheduler = Scheduler(engine, settings)
    scheduler.thread.start()
    return scheduler
