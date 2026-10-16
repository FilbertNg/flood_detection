"""Engine runner inside the API process: live mode and replay mode (build plan B3).

Holds the latest engine step (trigger, street states) and the alert log that the
API endpoints read. Replay walks an archived event at a chosen speed in a
background thread; speed=None runs it synchronously (tests, scripts).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable

import geopandas as gpd
import pandas as pd

from ..engine import replay
from ..engine.replay import ReplayStep
from ..engine.types import Reason
from ..ml import dataset

log = logging.getLogger(__name__)
STEP = timedelta(minutes=15)


@dataclass
class EngineContext:
    township: dict
    streets: gpd.GeoDataFrame                     # street_id, name, township_id, susceptibility, geometry
    stations: pd.DataFrame                        # lookup: graph_id, kind, name, lat, lon, thresholds
    rules_cfg: dict
    matrix: dict
    ml_cfg: dict
    tide: pd.DataFrame | None
    load_readings: Callable[[datetime, datetime], pd.DataFrame]          # archive (replay, live history)
    load_live_readings: Callable[[datetime], pd.DataFrame] | None         # live logs since a time
    bundle_for: Callable[[datetime, bool], dict | None]                   # (when, live) -> ML bundle
    forecast: Callable[[datetime], list[dict]] | None = None              # rain_next_12h for live mode
    radar: Callable[[datetime], Reason | None] | None = None              # informational radar_approaching (live only)


@dataclass
class Snapshot:
    mode: str
    step: ReplayStep | None
    alerts: list[dict]
    replay: dict | None
    readings: pd.DataFrame
    updated_at: datetime | None = None


def iso(dt: datetime) -> str:
    return pd.Timestamp(dt).strftime("%Y-%m-%dT%H:%M:%S+08:00")


@dataclass
class Runner:
    ctx: EngineContext
    mode: str = "live"
    _step: ReplayStep | None = None
    _alerts: list[dict] = field(default_factory=list)
    _replay: dict | None = None
    _readings: pd.DataFrame = field(default_factory=pd.DataFrame)
    _updated_at: datetime | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None
    _generation: int = 0   # bumped on every replay start/stop; a slower live refresh from an older generation is dropped

    # ---------- stations ----------
    @property
    def station_ids(self) -> list[str]:
        return [s["graph_id"] for s in self.ctx.township["stations"]]

    @property
    def wl_ids(self) -> list[str]:
        return [s["graph_id"] for s in self.ctx.township["stations"] if "WL" in s.get("types", [])]

    def _ml_rain_ids(self) -> list[str]:
        """Stations the ML features read: upstream river stations and rain gauges within 25 km (name kept for callers)."""
        return dataset.required_station_ids(self.ctx.stations, self.wl_ids)

    # ---------- engine ----------
    def _steps(self, start: datetime, end: datetime, readings: pd.DataFrame, live: bool):
        bundle = self.ctx.bundle_for(start, live)
        return replay.run(start, end, STEP, readings, self.ctx.stations, self.ctx.streets, self.station_ids,
                          self.ctx.rules_cfg, self.ctx.matrix, ml_bundle=bundle, ml_cfg=self.ctx.ml_cfg,
                          wl_ids=self.wl_ids, tide=self.ctx.tide)

    def _record(self, step: ReplayStep, is_replay: bool) -> None:
        with self._lock:
            self._step = step
            self._updated_at = datetime.now()
            for a in step.alerts:
                self._alerts.insert(0, {
                    "alert_id": f"{a.street_id}@{a.issued_at:%Y%m%dT%H%M}-{a.kind}",
                    "street_id": a.street_id, "horizon": "nowcast", "kind": a.kind, "level": a.level.json,
                    "issued_at": iso(a.issued_at),
                    "window": {"start": iso(a.window_start), "end": iso(a.window_end)} if a.window_start else None,
                    "outcome": "unverified", "is_replay": is_replay,
                })

    # ---------- live ----------
    def refresh_live(self, now: datetime | None = None) -> None:
        """Recompute live levels from the last 3 h of steps (alerts issued in that window are kept once)."""
        if self.mode != "live":
            return
        generation = self._generation
        now = pd.Timestamp(now or datetime.now()).floor("15min").to_pydatetime()
        since = now - timedelta(days=5)
        ids = set(self.station_ids) | set(self._ml_rain_ids())
        frames = [self.ctx.load_readings(since, now)]
        if self.ctx.load_live_readings is not None:
            frames.append(self.ctx.load_live_readings(since))
        readings = pd.concat([f for f in frames if len(f)], ignore_index=True) if any(len(f) for f in frames) else frames[0]
        readings = readings[readings.graph_id.isin(ids)].drop_duplicates(["graph_id", "kind", "time_local"], keep="last")
        last = None
        known = {a["alert_id"] for a in self._alerts}
        for step in self._steps(now - timedelta(hours=3), now, readings, live=True):
            last = step
        if last is None:
            return
        fresh = [a for a in last.alerts if f"{a.street_id}@{a.issued_at:%Y%m%dT%H%M}-{a.kind}" not in known]
        with self._lock:
            if self.mode != "live" or self._generation != generation:
                return  # a replay started (or stopped) while this refresh was computing
            self._readings = readings
        self._record(ReplayStep(time=last.time, trigger=last.trigger, states=last.states, alerts=fresh), is_replay=False)

    # ---------- replay ----------
    def start_replay(self, event: date, speed: float | None, start: str = "06:00", end: str = "14:00",
                     stop_at: str | None = None) -> None:
        self.stop_replay(keep_mode=True)
        t0 = datetime.fromisoformat(f"{event} {start}")
        t1 = datetime.fromisoformat(f"{event} {stop_at or end}")
        ids = sorted(set(self.station_ids) | set(self._ml_rain_ids()))
        readings = self.ctx.load_readings(t0 - timedelta(days=5), datetime.fromisoformat(f"{event} {end}"))
        readings = readings[readings.graph_id.isin(ids)]
        with self._lock:
            self._generation += 1
            self.mode = "replay"
            self._alerts = [a for a in self._alerts if not a["is_replay"]]
            self._replay = {"event": str(event), "speed": speed or 0}
            self._readings = readings
        steps = self._steps(t0, t1, readings, live=False)
        if not speed:
            for step in steps:
                self._record(step, is_replay=True)
            return
        self._stop.clear()
        generation = self._generation

        def worker():
            for step in steps:
                if self._stop.is_set() or self._generation != generation:
                    return
                self._record(step, is_replay=True)
                self._stop.wait(STEP.total_seconds() / speed)

        self._thread = threading.Thread(target=worker, daemon=True, name="replay")
        self._thread.start()

    def stop_replay(self, keep_mode: bool = False) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if not keep_mode:
            with self._lock:
                self._generation += 1
                self.mode, self._replay = "live", None
                self._alerts = [a for a in self._alerts if not a["is_replay"]]
                self._step = None

    def snapshot(self) -> Snapshot:
        with self._lock:
            return Snapshot(mode=self.mode, step=self._step, alerts=list(self._alerts), replay=self._replay,
                            readings=self._readings, updated_at=self._updated_at)
