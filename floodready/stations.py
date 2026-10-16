"""Station lookup: one row per (graph_id, kind) with name, district, thresholds
and coordinates.

Infobanjir's live tables have names and thresholds but no coordinates; the
frozen data.gov.my station list has coordinates. Its station_id usually equals
the Infobanjir graph ID (e.g. 26558), and its station_code sometimes does
(e.g. PEKANMERU).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

LOOKUP_COLUMNS = ["graph_id", "kind", "station_code", "name", "district", "state", "lat", "lon",
                  "wl_normal_m", "wl_alert_m", "wl_warning_m", "wl_danger_m", "thresholds_ok"]


def _coordinates(live: pd.DataFrame, old: pd.DataFrame) -> pd.DataFrame:
    old = old.assign(sid=old["station_id"].astype(str).str.strip("_"))
    by_sid = old.drop_duplicates("sid").set_index("sid")[["latitude", "longitude"]]
    by_code = old.drop_duplicates("station_code").set_index("station_code")[["latitude", "longitude"]]
    lat, lon = [], []
    for graph_id, code in zip(live["graph_id"].astype(str), live["station_code"].astype(str)):
        hit = None
        for table, key in ((by_sid, graph_id.strip("_")), (by_code, graph_id), (by_sid, code.strip("_")), (by_code, code)):
            if key in table.index:
                hit = table.loc[key]
                break
        lat.append(np.nan if hit is None else float(hit["latitude"]))
        lon.append(np.nan if hit is None else float(hit["longitude"]))
    return pd.DataFrame({"lat": lat, "lon": lon}, index=live.index)


def build_lookup(wl_live: pd.DataFrame, rf_live: pd.DataFrame, old: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for kind, live in (("wl", wl_live), ("rf", rf_live)):
        live = live.drop_duplicates("graph_id").reset_index(drop=True)
        frame = pd.DataFrame({
            "graph_id": live["graph_id"].astype(str), "kind": kind,
            "station_code": live["station_code"], "name": live["station_name"],
            "district": live["district"], "state": live["state"],
        })
        for col in ("wl_normal_m", "wl_alert_m", "wl_warning_m", "wl_danger_m"):
            frame[col] = live[col] if col in live else np.nan
        frames.append(pd.concat([frame, _coordinates(live, old)], axis=1))
    lookup = pd.concat(frames, ignore_index=True)
    ordered = (lookup.wl_normal_m < lookup.wl_alert_m) & (lookup.wl_alert_m < lookup.wl_warning_m) & (lookup.wl_warning_m < lookup.wl_danger_m)
    lookup["thresholds_ok"] = np.where(lookup.kind == "wl", ordered, True)
    return lookup[LOOKUP_COLUMNS]


_warned = False


def load_default(path=None) -> pd.DataFrame | None:
    """The station table at data/interim/stations.parquet (scripts/build_station_lookup.py), or None if it is not built.
    Used by the readings loaders so QC rules that need station coordinates work without callers passing the table.
    A missing table switches the wl_unresponsive QC rule off; that is logged once per process."""
    global _warned
    from pathlib import Path
    path = Path(path) if path else Path(__file__).resolve().parents[1] / "data" / "interim" / "stations.parquet"
    if path.exists():
        return pd.read_parquet(path)
    if not _warned:
        _warned = True
        logging.getLogger(__name__).warning("%s not found: QC rule wl_unresponsive is skipped (run scripts/build_station_lookup.py)", path)
    return None
