"""ResultCache: recent results of the slow admin statistics and report, refreshed in the background when old."""
import pytest

from floodready.api.result_cache import ResultCache


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make(fresh=300, size=32):
    clock, spawned = Clock(), []
    cache = ResultCache(fresh=fresh, size=size, clock=clock, spawn=spawned.append)
    return cache, clock, spawned


def counter(*values):
    calls = []

    def compute():
        calls.append(1)
        return values[min(len(calls), len(values)) - 1]
    return compute, calls


def test_a_miss_computes_and_a_hit_does_not():
    cache, _, spawned = make()
    compute, calls = counter("a")
    assert cache.get("k", compute) == "a"
    assert cache.get("k", compute) == "a"
    assert len(calls) == 1 and spawned == []


def test_an_old_result_is_served_and_refreshed_in_the_background():
    cache, clock, spawned = make(fresh=300)
    compute, calls = counter("old", "new")
    cache.get("k", compute)
    clock.t = 301
    assert cache.get("k", compute) == "old"                 # served at once
    assert len(spawned) == 1
    assert cache.get("k", compute) == "old" and len(spawned) == 1    # one refresh per key at a time
    spawned[0]()
    assert cache.get("k", compute) == "new"
    assert len(calls) == 2


def test_clear_makes_the_next_request_recompute():
    cache, _, _ = make()
    compute, calls = counter("a", "b")
    cache.get("k", compute)
    cache.clear()
    assert cache.get("k", compute) == "b"


def test_a_refresh_started_before_clear_is_not_stored():
    cache, clock, spawned = make(fresh=300)
    compute, _ = counter("old", "computed-before-the-write", "after")
    cache.get("k", compute)
    clock.t = 301
    cache.get("k", compute)
    cache.clear()                                            # a write landed while the refresh was running
    spawned[0]()
    assert cache.get("k", compute) == "after"


def test_a_failed_refresh_keeps_the_old_result():
    cache, clock, spawned = make(fresh=300)
    state = {"fail": False}

    def compute():
        if state["fail"]:
            raise RuntimeError("database locked")
        return "old"
    cache.get("k", compute)
    clock.t = 301
    state["fail"] = True
    cache.get("k", compute)
    spawned[0]()                                             # logged, not raised
    state["fail"] = False
    assert cache.get("k", compute) == "old"
    assert len(spawned) == 2                                 # still old, so another refresh is tried


def test_a_failed_miss_raises_and_stores_nothing():
    cache, _, _ = make()

    def boom():
        raise RuntimeError("x")
    with pytest.raises(RuntimeError):
        cache.get("k", boom)
    assert cache.get("k", lambda: "ok") == "ok"


def test_put_stores_a_precomputed_result():
    cache, _, _ = make()
    cache.put("k", "warm")
    assert cache.get("k", lambda: "cold") == "warm"


def test_the_oldest_key_is_dropped_beyond_size():
    cache, clock, _ = make(size=2)
    for i, k in enumerate("abc"):
        clock.t = i
        cache.get(k, lambda k=k: k)
    compute, calls = counter("a2")
    assert cache.get("a", compute) == "a2" and len(calls) == 1
