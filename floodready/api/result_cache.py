"""Recent results of slow read-only endpoints: the admin statistics and monthly report (up to ~15 s over the whole
archive on the server, so a visitor would think the page is stuck).

A cached result is served at once. One older than `fresh` seconds is recomputed in the background, so the next
request is current; the engine adds alert rows every 15 min and station health counts slots up to now, so a result
is never more than one refresh behind. `clear()` drops everything; the API calls it after every write that feeds
the statistics (answers, reviews, suggestions, notes), and a refresh that started before the clear is discarded.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Hashable
from typing import Any

log = logging.getLogger(__name__)


def _thread(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, daemon=True, name="result-cache").start()


class ResultCache:
    def __init__(self, fresh: float = 300, size: int = 32, clock: Callable[[], float] = time.monotonic,
                 spawn: Callable[[Callable[[], None]], None] = _thread):
        self.fresh, self.size, self.clock, self.spawn = fresh, size, clock, spawn
        self._lock = threading.Lock()
        self._entries: dict[Hashable, tuple[float, Any]] = {}     # key -> (computed at, value), oldest first
        self._refreshing: set[Hashable] = set()
        self._key_locks: dict[Hashable, threading.Lock] = {}
        self._generation = 0

    def get(self, key: Hashable, compute: Callable[[], Any]) -> Any:
        with self._lock:
            hit = self._entries.get(key)
            if hit is not None:
                if self.clock() - hit[0] > self.fresh and key not in self._refreshing:
                    self._refreshing.add(key)
                    generation = self._generation
                    self.spawn(lambda: self._refresh(key, compute, generation))
                return hit[1]
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:                                  # a second request for the same key waits, then hits
            with self._lock:
                hit = self._entries.get(key)
            if hit is not None:
                return hit[1]
            with self._lock:
                generation = self._generation
            value = compute()
            self._store(key, value, generation)
            return value

    def put(self, key: Hashable, value: Any) -> None:
        with self._lock:
            generation = self._generation
        self._store(key, value, generation)

    def clear(self) -> None:
        with self._lock:
            self._generation += 1
            self._entries.clear()

    def _refresh(self, key: Hashable, compute: Callable[[], Any], generation: int) -> None:
        try:
            self._store(key, compute(), generation)
        except Exception:
            log.exception("background refresh of %r failed; the old result stays", key)
        finally:
            with self._lock:
                self._refreshing.discard(key)

    def _store(self, key: Hashable, value: Any, generation: int) -> None:
        with self._lock:
            if generation != self._generation:          # computed from data older than the last write
                return
            self._entries.pop(key, None)
            self._entries[key] = (self.clock(), value)
            while len(self._entries) > self.size:
                self._entries.pop(next(iter(self._entries)))
