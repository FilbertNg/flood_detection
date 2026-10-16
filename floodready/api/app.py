"""Production wiring: build the engine context from the repo's data and expose `app`.

uvicorn floodready.api.app:app --port 8000
Environment: TOWNSHIP (default BBR), ADMIN_EMAIL, ADMIN_PASSWORD, JWT_SECRET, CORS_ORIGINS.
"""
from __future__ import annotations

import glob
import os
import threading
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

from .. import live, radar
from ..engine import street_stations
from ..engine.replay import load_archive_readings
from ..ml import dataset, forecast as river, predict
from .main import create_app
from .runner import EngineContext, Runner, iso

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


def build_context(township_id: str = "BBR") -> EngineContext:
    town = next(t for t in _yaml("townships.yaml")["townships"] if t["id"] == township_id)
    stations = pd.read_parquet(DATA / "interim" / "stations.parquet")
    streets = gpd.read_file(ROOT / "assets" / "geo" / f"{township_id.lower()}_streets.geojson")
    wl_ids = [s["graph_id"] for s in town["stations"] if "WL" in s.get("types", [])]
    hist = DATA / "raw" / "jps_hist"
    archived = {p.stem for p in (hist / "rf").glob("*.parquet")} | {p.stem for p in (hist / "wl").glob("*.parquet")}
    ids = sorted((set(s["graph_id"] for s in town["stations"]) | set(dataset.rain_stations_near(stations, wl_ids, 25))) & archived)

    @lru_cache(maxsize=1)
    def archive() -> pd.DataFrame:
        return load_archive_readings(hist, ids, datetime(2024, 1, 1), datetime(2100, 1, 1))

    def load_readings(start: datetime, end: datetime) -> pd.DataFrame:
        a = archive()
        return a[(a.time_local >= pd.Timestamp(start)) & (a.time_local <= pd.Timestamp(end))]

    def load_live(since: datetime) -> pd.DataFrame:
        return live.load_live_readings(DATA / "raw" / "jps_live", since, set(ids))

    def forecast(at: datetime) -> list[dict]:
        files = sorted(glob.glob(str(DATA / "raw" / "openmeteo_live" / "*.parquet")))
        if not files:
            return []
        f = pd.read_parquet(files[-1])
        f = f[(f.point_id == township_id) & (f.model == "best_match")]
        if f.empty:
            return []
        f = f[f.fetched_at_local == f.fetched_at_local.max()]
        f = f[(f.time_local > pd.Timestamp(at)) & (f.time_local <= pd.Timestamp(at) + timedelta(hours=12))]
        return [{"time": iso(t), "mm": float(mm or 0)} for t, mm in zip(f.time_local, f.precip_mm)]

    tide_path = DATA / "interim" / "tide_hourly.parquet"
    tide = pd.read_parquet(tide_path) if tide_path.exists() else None

    bundles = river.BundleCache(ROOT / "models")
    river_cache: dict = {}
    river_lock = threading.Lock()

    def river_forecast(readings: pd.DataFrame, graph_id: str, at: datetime, is_live: bool) -> dict | None:
        """Forecast from the station's latest level (at most 30 min old); the replay uses the fold model
        that never trained on that period."""
        key = (graph_id, pd.Timestamp(at).floor("15min"), is_live)
        with river_lock:
            if key in river_cache:
                return river_cache[key]
        bundle = bundles.get(at, is_live)
        out = river.forecast_from_readings(bundle, readings, stations, tide, graph_id, at) if bundle else None
        if bundle is not None:                      # a missing model is retried later, never cached here
            with river_lock:
                if len(river_cache) >= 64:
                    river_cache.pop(next(iter(river_cache)))
                river_cache[key] = out
        return out

    return EngineContext(
        township=town, streets=streets[["street_id", "name", "township_id", "susceptibility", "geometry"]],
        stations=stations, rules_cfg=_yaml("rules.yaml"), matrix=_yaml("risk_matrix.yaml")["matrix"],
        ml_cfg=_yaml("ml.yaml"), tide=tide,
        load_readings=load_readings, load_live_readings=load_live,
        bundle_for=lambda when, is_live: predict.bundle_for(ROOT / "models", when, live=is_live),
        radar=lambda now: radar.latest_reason(DATA / "raw" / "radar", town["centre"]["lat"], town["centre"]["lon"], now),
        street_stations=street_stations.load(ROOT / "assets" / "geo" / f"{township_id.lower()}_street_stations.json"),
        forecast=forecast, river_forecast=river_forecast,
    )


app = create_app(Runner(build_context(os.environ.get("TOWNSHIP", "BBR"))))
