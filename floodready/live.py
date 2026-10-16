"""Turn the logged Infobanjir live tables into 15-min engine readings.

Water level: the reading at its source time. Rain: the live table gives
"rain since midnight", so rain per interval is the difference between
successive readings (after midnight the new day's total is the interval).
"""
from __future__ import annotations

import glob
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from . import qc
from . import stations as stations_mod

COLUMNS = ["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"]

# History QC needs before the live window: the longest rule window is 24 h (rain_stuck, counter rebound);
# the 4.5 h wl_unresponsive run and the 3 h rain sums are shorter. 2 days leaves a full extra day of margin.
ARCHIVE_TAIL_DAYS = 2
_TAIL_CACHE_DAYS = 30          # how much of each archive file is kept in memory
_TAIL_CACHE: dict[tuple, pd.DataFrame] = {}
log = logging.getLogger(__name__)


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


def _archive_tail(hist_dir: Path, graph_ids: set[str] | None, start: pd.Timestamp) -> pd.DataFrame:
    """Raw archive rows (engine columns) from `start` on, for the given gauges. Each file's recent rows are
    cached against its mtime and size, so a 15-min tick re-reads only files the archiver has touched."""
    frames = []
    for kind, value in (("rf", "rain_15min_mm"), ("wl", "wl_m")):
        for path in sorted((Path(hist_dir) / kind).glob("*.parquet")):
            if graph_ids is not None and path.stem not in graph_ids:
                continue
            stat = path.stat()
            key = (str(path), stat.st_mtime_ns, stat.st_size)
            tail = _TAIL_CACHE.get(key)
            if tail is None:
                for old in [k for k in _TAIL_CACHE if k[0] == key[0]]:
                    del _TAIL_CACHE[old]
                df = pd.read_parquet(path, columns=["time_local", value])
                tail = df[df.time_local >= df.time_local.max() - pd.Timedelta(days=_TAIL_CACHE_DAYS)] if len(df) else df
                _TAIL_CACHE[key] = tail
            tail = tail[tail.time_local >= start]
            if tail.empty:
                continue
            frames.append(pd.DataFrame({"graph_id": path.stem, "kind": kind, "time_local": tail.time_local,
                                        "rain_15min_mm": tail[value] if kind == "rf" else float("nan"),
                                        "wl_m": tail[value] if kind == "wl" else float("nan")}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)


def load_live_readings(live_dir: Path, since: datetime, graph_ids: set[str] | None = None,
                       stations: pd.DataFrame | None = None, archive_dir: Path | None = None,
                       until: datetime | None = None) -> pd.DataFrame:
    """Readings from data/raw/jps_live/{wl,rf}/<date>.parquet since `since`, after QC.
    `stations` (coordinates) enables wl_unresponsive; default: data/interim/stations.parquet if built.

    `archive_dir` (data/raw/jps_hist): QC runs over the last ARCHIVE_TAIL_DAYS of the archive plus the live
    readings (live wins on the same gauge, kind and time), as replay and training do over the full archive, so
    a gauge stuck for longer than the live window is judged the same way. Only rows from `since` come back.
    `until` drops everything after it before QC (nothing after t is ever used). A missing archive is logged
    once and QC then covers the live readings only."""
    tail = pd.DataFrame(columns=COLUMNS)
    if archive_dir is not None:
        if (Path(archive_dir) / "rf").is_dir() or (Path(archive_dir) / "wl").is_dir():
            tail = _archive_tail(archive_dir, graph_ids, pd.Timestamp(since) - pd.Timedelta(days=ARCHIVE_TAIL_DAYS))
        else:
            log.warning("archive %s not found: live QC covers the live window only", archive_dir)
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
    if not frames and tail.empty:
        return pd.DataFrame(columns=COLUMNS)
    # live first, so keep="first" lets a live reading replace the archive's for the same gauge, kind and time
    both = pd.concat([f for f in [*frames, tail] if len(f)], ignore_index=True)
    both = both.drop_duplicates(["graph_id", "kind", "time_local"], keep="first")
    if until is not None:
        both = both[both.time_local <= pd.Timestamp(until)]
    out, _ = qc.clean_readings(both, stations=stations if stations is not None else stations_mod.load_default())  # on the full span, then cut
    return out[out.time_local >= pd.Timestamp(since)].reset_index(drop=True)
