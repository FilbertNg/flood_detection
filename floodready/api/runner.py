"""Engine runner inside the API process: live mode and replay mode (build plan B3).

Holds the latest engine step (trigger, street states). Street states and alerts are persisted through the
repository (`floodready.db.repo`), the API endpoints read alerts back from the database, and new alerts that
should be pushed go to `PushService`. Replay walks an archived event at a chosen speed in a
background thread; speed=None runs it synchronously (tests, scripts).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Callable

import geopandas as gpd
import pandas as pd
from sqlalchemy import Engine

from ..engine import alerts as alerts_mod, outlook, replay
from ..engine.alerts import LIVE_WINDOW_MIN
from ..engine.replay import ReplayStep
from ..db import repo
from ..engine.types import Alert, Level, Reason
from ..ml import dataset
from ..push import PushService

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
    street_stations: dict | None = None                                   # street_id -> {wl, rf, method, distance_m}; None = township-wide trigger
    # (readings, graph_id, at, live) -> RiverForecast dict | None; the station's level at +1 h / +2 h
    river_forecast: Callable[[pd.DataFrame, str, datetime, bool], dict | None] | None = None
    # (now) -> (parsed MET warnings, hourly forecast DataFrame time_local/precip_mm) for the 6-24 h Outlook (live only)
    outlook_inputs: Callable[[datetime], tuple[list[dict], pd.DataFrame]] | None = None
    tide_loader: Callable[[], pd.DataFrame | None] | None = None          # current tide table (reloads when the file changes); wins over `tide`

    def tide_table(self) -> pd.DataFrame | None:
        return self.tide_loader() if self.tide_loader is not None else self.tide


@dataclass
class Snapshot:
    mode: str
    step: ReplayStep | None
    replay: dict | None
    readings: pd.DataFrame
    updated_at: datetime | None = None
    alerts_loader: Callable[..., list[dict]] | None = None     # reads the database only when alerts are asked for

    @property
    def alerts(self) -> list[dict]:
        return self.alerts_loader() if self.alerts_loader else []

    def alerts_for(self, street_id: str) -> list[dict]:
        return self.alerts_loader(street_id=street_id) if self.alerts_loader else []


def iso(dt: datetime) -> str:
    return pd.Timestamp(dt).strftime("%Y-%m-%dT%H:%M:%S+08:00")


@dataclass
class Runner:
    ctx: EngineContext
    db: Engine | None = None            # SQLAlchemy engine; default is a private in-memory SQLite (tests, scripts)
    push: PushService | None = None     # default: built from the VAPID_* environment variables
    mode: str = "live"
    _step: ReplayStep | None = None
    _replay: dict | None = None
    _readings: pd.DataFrame = field(default_factory=pd.DataFrame)
    _updated_at: datetime | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None
    _generation: int = 0   # bumped on every replay start/stop; a slower live refresh from an older generation is dropped
    _db_lock: threading.RLock = field(default_factory=threading.RLock)
    _outlook_last: Alert | None = None                           # the township's last outlook row (alert or all_clear)
    _outlook_streets: list[str] = field(default_factory=list)    # streets that carry the active outlook

    def __post_init__(self):
        alerts_mod.validate_config(self.ctx.rules_cfg["alerts"])    # a bad config fails at boot, not in GET /alerts
        if self.db is None:
            self.db = repo.connect("sqlite://")
        if self.push is None:
            self.push = PushService(self.db)
        self.push.warn_if_disabled()
        self._street_names = dict(zip(self.ctx.streets.street_id, self.ctx.streets.name))
        try:   # restart mid-outlook: keep the active outlook and its cooldown instead of re-issuing it
            with self._db_lock, self.db.begin() as conn:
                self._outlook_last, self._outlook_streets = repo.latest_outlook(conn, self.ctx.township["id"])
        except Exception:
            log.exception("could not reseed the outlook state")

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
                          wl_ids=self.wl_ids, tide=self.ctx.tide_table(), street_stations=self.ctx.street_stations)

    def _record(self, step: ReplayStep, is_replay: bool) -> None:
        """Persist the step's states and alerts, then push the alerts that are new (not seen before in the database)."""
        mode = "replay" if is_replay else "live"
        reasons = {(a.street_id, iso(a.issued_at), a.level.json): a.reasons[0] for a in step.alerts if a.reasons}
        with self._db_lock:
            with self.db.begin() as conn:
                repo.save_street_states(conn, step.states, mode)
                new_ids = set(repo.insert_alerts(conn, step.alerts, is_replay=is_replay, is_backfill=False))
                new = []
                if new_ids:
                    since = min(a.issued_at for a in step.alerts)
                    new = [a for a in repo.list_alerts(conn, include_replay=True, since=since) if a["alert_id"] in new_ids]
        with self._lock:
            self._step = step
            self._updated_at = datetime.now()
        for a in new:
            r = reasons.get((a["street_id"], a["issued_at"], a["level"]))
            if r is not None:
                a["reason_text"] = {"en": r.text_en, "ms": r.text_ms}
        self.push.enqueue([a for a in new if a["push"]], self._street_names)

    def alerts(self, street_id: str | None = None, active: bool = False) -> list[dict]:
        """AlertSummary list from the database: live rows in live mode, replay rows only while a replay is on."""
        with self._lock:
            replaying = self.mode == "replay"
        with self._db_lock, self.db.begin() as conn:
            return repo.list_alerts(conn, street_id=street_id, active=active, include_replay=replaying, replay_only=replaying)

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
        for step in self._steps(now - timedelta(minutes=LIVE_WINDOW_MIN), now, readings, live=True):
            last = step
        if last is None:
            return
        with self._lock:
            if self.mode != "live" or self._generation != generation:
                return  # a replay started (or stopped) while this refresh was computing
            self._readings = readings
        self._record(ReplayStep(time=last.time, trigger=last.trigger, states=last.states, alerts=last.alerts), is_replay=False)
        self._refresh_outlook(now, last.states, generation)

    def _refresh_outlook(self, now: datetime, states, generation: int) -> None:
        """6-24 h Outlook (E8): one township alert, stored per street at Watch only where the nowcast level is Normal."""
        if self.ctx.outlook_inputs is None:
            return
        try:
            warnings, forecast = self.ctx.outlook_inputs(now)
            cfg = {**self.ctx.rules_cfg, "township": self.ctx.township}
            issued = outlook.issue_outlook(outlook.township_outlook(warnings, forecast, now, cfg), self._outlook_last, now, cfg)
        except Exception:  # advisory: must never break the live nowcast
            log.exception("outlook failed")
            return
        if issued is None:
            return
        streets = ([s.street_id for s in states if s.level == Level.NORMAL] if issued.kind == "alert"
                   else list(self._outlook_streets))
        alerts = [replace(issued, street_id=sid) for sid in streets]
        if not alerts or self.mode != "live" or self._generation != generation:
            return
        with self._db_lock:
            with self.db.begin() as conn:
                new_ids = set(repo.insert_alerts(conn, alerts, is_replay=False, is_backfill=False, horizon="outlook"))
                new = ([a for a in repo.list_alerts(conn, include_replay=False, since=now) if a["alert_id"] in new_ids]
                       if new_ids else [])
        self._outlook_last, self._outlook_streets = issued, (streets if issued.kind == "alert" else [])
        if issued.reasons:   # one push text that names every trigger (MET warning and forecast)
            text = {"en": " ".join(r.text_en for r in issued.reasons), "ms": " ".join(r.text_ms for r in issued.reasons)}
            for a in new:
                a["reason_text"] = text
        self.push.enqueue([a for a in new if a["push"]], self._street_names)

    # ---------- replay ----------
    def start_replay(self, event: date, speed: float | None, start: str = "06:00", end: str = "14:00",
                     stop_at: str | None = None) -> None:
        self.stop_replay(keep_mode=True)
        t0 = datetime.fromisoformat(f"{event} {start}")
        t1 = datetime.fromisoformat(f"{event} {stop_at or end}")
        ids = sorted(set(self.station_ids) | set(self._ml_rain_ids()))
        readings = self.ctx.load_readings(t0 - timedelta(days=5), datetime.fromisoformat(f"{event} {end}"))
        readings = readings[readings.graph_id.isin(ids)]
        with self._db_lock, self.db.begin() as conn:
            files = repo.clear_replay(conn)       # a rehearsal re-issues (and re-pushes) every alert of the event
        repo.remove_files(files)                  # demo photos, only after the commit
        with self._lock:
            self._generation += 1
            self.mode = "replay"
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
                self._step = None
            with self._db_lock, self.db.begin() as conn:
                files = repo.clear_replay(conn)
            repo.remove_files(files)

    def snapshot(self) -> Snapshot:
        with self._lock:
            snap = dict(mode=self.mode, step=self._step, replay=self._replay, readings=self._readings,
                        updated_at=self._updated_at)
        return Snapshot(alerts_loader=self.alerts, **snap)
