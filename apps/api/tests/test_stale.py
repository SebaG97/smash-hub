import pytest

from app.core import stale


def test_stale_copy_answers_while_refreshing(monkeypatch):
    queued = []
    monkeypatch.setattr(stale, "spawn", queued.append)
    store, answers = {}, iter(["first", "second"])

    def load():
        return next(answers)

    assert stale.cached(store, "k", 60, load) == "first"
    assert stale.cached(store, "k", 60, load) == "first" and not queued  # fresh
    store["k"] = (store["k"][0] - 61, "first")  # expire it
    assert stale.cached(store, "k", 60, load) == "first"  # no wait for start.gg
    assert stale.cached(store, "k", 60, load) == "first"
    assert len(queued) == 1  # a single refresh at a time
    queued.pop()()
    assert stale.cached(store, "k", 60, load) == "second"


def test_failed_refresh_keeps_the_last_copy(monkeypatch):
    queued = []
    monkeypatch.setattr(stale, "spawn", queued.append)
    store = {"k": (-1e9, "old")}

    def load():
        raise RuntimeError("start.gg is down")

    assert stale.cached(store, "k", 60, load) == "old"
    queued.pop()()
    assert store["k"][1] == "old"
    assert stale.cached(store, "k", 60, load) == "old" and len(queued) == 1


def test_first_load_errors_reach_the_caller():
    def load():
        raise RuntimeError("start.gg is down")

    with pytest.raises(RuntimeError):
        stale.cached({}, "k", 60, load)
