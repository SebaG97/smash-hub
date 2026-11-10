"""In-memory caches of slow start.gg answers that never make a reader wait for a refresh.

A fresh copy is served as is. A stale one is served right away while a background thread
asks start.gg again, so a page that loaded once keeps loading even when start.gg is slow
(a bracket takes ~20 s at its rate limit) or down. Only a key never fetched waits.
"""

import logging
import threading
import time

log = logging.getLogger(__name__)

_lock = threading.Lock()
_refreshing: set = set()


def spawn(target):
    """Run target in a daemon thread (tests replace it to run inline)."""
    threading.Thread(target=target, daemon=True, name="stale-refresh").start()


def cached(store: dict, key, seconds: float, load):
    """store[key] holds (monotonic time, value); load() fetches a new value."""
    hit = store.get(key)
    if hit is None:
        value = load()
        store[key] = (time.monotonic(), value)
        return value
    if time.monotonic() - hit[0] >= seconds:
        token = (id(store), key)
        with _lock:
            start = token not in _refreshing
            _refreshing.add(token)
        if start:

            def refresh():
                try:
                    store[key] = (time.monotonic(), load())
                except Exception:  # keep serving the last copy
                    log.warning("refresh of %s failed; serving the last copy", key, exc_info=True)
                finally:
                    with _lock:
                        _refreshing.discard(token)

            spawn(refresh)
    return hit[1]
