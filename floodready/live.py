"""Turn the logged Infobanjir live tables into 15-min engine readings.

Water level: the reading at its source time. Rain: the live table gives
"rain since midnight", so rain per interval is the difference between
successive readings (after midnight the new day's total is the interval).
"""
from __future__ import annotations

import glob
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from . import qc

COLUMNS = ["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"]


def rain_readings(rf: pd.DataFrame) -> pd.DataFrame:
    out = []
    for graph_id, g in rf.dropna(subset=["source_time"]).groupby("graph_id"):
        if "fetched_at_local" in g:
            g = g.sort_values("fetched_at_local")
        g = g.drop_duplicates("source_time", keep="last").sort_values("source_time")
        total, prev_total = g["rain_since_midnight_mm"], g["rain_since_midnight_mm"].shift(1)
        new_day = g["source_time"].dt.date != g["source_time"].shift(1).dt.date
        rain = (total - prev_total).where(~new_day, total)
        rain = rain.where(rain >= 0, total)  # a station reset mid-day: take its new total
        frame = pd.DataFrame({"graph_id": graph_id, "kind": "rf", "time_local": g["source_time"],
                              "rain_15min_mm": rain, "wl_m": float("nan")}).iloc[1:]
        out.append(frame)
    return pd.concat(out, ignore_index=True)[COLUMNS] if out else pd.DataFrame(columns=COLUMNS)


def level_readings(wl: pd.DataFrame) -> pd.DataFrame:
    wl = wl.dropna(subset=["source_time"])
    if "fetched_at_local" in wl:  # a later fetch of the same reading wins (JPS corrects 0.00 placeholders)
        wl = wl.sort_values("fetched_at_local")
    wl = wl.drop_duplicates(["graph_id", "source_time"], keep="last")
    return pd.DataFrame({"graph_id": wl["graph_id"], "kind": "wl", "time_local": wl["source_time"],
                         "rain_15min_mm": float("nan"), "wl_m": wl["wl_m"]})[COLUMNS].reset_index(drop=True)


def load_live_readings(live_dir: Path, since: datetime, graph_ids: set[str] | None = None) -> pd.DataFrame:
    """Readings from data/raw/jps_live/{wl,rf}/<date>.parquet since `since`."""
    frames = []
    for kind, convert in (("wl", level_readings), ("rf", rain_readings)):
        files = [f for f in sorted(glob.glob(str(Path(live_dir) / kind / "*.parquet")))
                 if Path(f).stem >= (since - timedelta(days=1)).strftime("%Y-%m-%d")]
        if not files:
            continue
        df = pd.concat(pd.read_parquet(f) for f in files)
        if graph_ids is not None:
            df = df[df.graph_id.isin(graph_ids)]
        frames.append(convert(df))
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    out, _ = qc.clean_readings(pd.concat(frames, ignore_index=True))  # on the full loaded span, then cut
    return out[out.time_local >= pd.Timestamp(since)]
