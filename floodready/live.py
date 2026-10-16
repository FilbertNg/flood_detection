"""Turn the logged Infobanjir live tables into 15-min engine readings.

Water level: the reading at its source time. Rain: the live table gives
"rain since midnight", so rain per interval is the difference between
successive readings (after midnight the new day's total is the interval).
"""
from __future__ import annotations

import glob
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa

from . import qc
from . import stations as stations_mod

COLUMNS = ["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"]

# History QC needs before the live window: the longest rule look-back (wl_unresponsive runs, dead-gauge state,
# monthly rain). Measured on the real archive: this tail gives 0 mismatches against full-history QC.
ARCHIVE_TAIL_DAYS = qc.QC_HISTORY_DAYS
# Cached per archive file: the tail plus the runner's `since` offset (5 days) with margin.
_TAIL_CACHE_DAYS = ARCHIVE_TAIL_DAYS + 10
_TAIL_CACHE: dict[str, tuple] = {}              # path -> ((mtime_ns, size), cached_from, rows)
_TAIL_LOCK = threading.Lock()                   # refresh_live can run in two threads
_warned_no_archive = False
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


def _read_tail(path: Path, value: str, start: pd.Timestamp) -> pd.DataFrame | None:
    """The cached recent rows of one archive file (`time_local`, `value`), or None when it cannot be read and
    nothing is cached. The cache entry is keyed on mtime and size and covers at least `start` onwards."""
    try:
        stat = path.stat()
        sig = (stat.st_mtime_ns, stat.st_size)
        hit = _TAIL_CACHE.get(str(path))
        if hit is not None and hit[0] == sig and hit[1] <= start:
            return hit[2]
        df = pd.read_parquet(path, columns=["time_local", value])
        cutoff = min(start, df.time_local.max() - pd.Timedelta(days=_TAIL_CACHE_DAYS)) if len(df) else start
        tail = df[df.time_local >= cutoff]
        _TAIL_CACHE[str(path)] = (sig, cutoff, tail)
        return tail
    except (OSError, ValueError, pa.ArrowException) as exc:       # rebuilt or torn file: one bad gauge must not stop the tick
        log.warning("archive file %s unreadable (%s); %s", path, exc, "using its cached rows" if str(path) in _TAIL_CACHE else "skipped")
        hit = _TAIL_CACHE.get(str(path))
        return hit[2] if hit is not None else None


def _archive_tail(hist_dir: Path, graph_ids: set[str] | None, start: pd.Timestamp) -> pd.DataFrame:
    """Raw archive rows (engine columns) from `start` on, for the given gauges. Each file's recent rows are
    cached against its mtime and size, so a 15-min tick re-reads only files the archiver has touched."""
    frames = []
    with _TAIL_LOCK:
        for kind, value in (("rf", "rain_15min_mm"), ("wl", "wl_m")):
            for path in sorted((Path(hist_dir) / kind).glob("*.parquet")):
                if graph_ids is not None and path.stem not in graph_ids:
                    continue
                tail = _read_tail(path, value, start)
                if tail is None:
                    continue
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
    """Live readings (data/raw/jps_live/{wl,rf}/<date>.parquet) from `since`, after QC.
    `stations` (coordinates) enables wl_unresponsive; default: data/interim/stations.parquet if built.

    `archive_dir` (data/raw/jps_hist): QC runs over the last ARCHIVE_TAIL_DAYS of the archive plus the live
    readings, as replay and training do over the full archive, so a gauge stuck for longer than the live window
    is judged the same way. For the same gauge, kind and time the archive value wins (it is JPS's later,
    corrected record; live 0.00 placeholders lose) and live fills what the archive lacks. Only rows from the
    first live reading come back: earlier rows already have the runner's full-history QC and must not be
    replaced by a shorter-history copy. `until` drops everything after it before QC (nothing after t is used).
    A missing archive is logged once per process and QC then covers the live readings only."""
    global _warned_no_archive
    tail = pd.DataFrame(columns=COLUMNS)
    since_ts = pd.Timestamp(since)
    if archive_dir is not None:
        if (Path(archive_dir) / "rf").is_dir() or (Path(archive_dir) / "wl").is_dir():
            tail = _archive_tail(archive_dir, graph_ids, since_ts - pd.Timedelta(days=ARCHIVE_TAIL_DAYS))
        elif not _warned_no_archive:
            _warned_no_archive = True
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
    frames = [f for f in frames if len(f)]
    if until is not None:
        frames = [f[f.time_local <= pd.Timestamp(until)] for f in frames]
        tail = tail[tail.time_local <= pd.Timestamp(until)]
    lv = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    lv = lv[lv.time_local >= since_ts]
    if lv.empty:
        return pd.DataFrame(columns=COLUMNS)
    first_live = lv.time_local.min()
    both = pd.concat([f for f in (tail.assign(_src=0), lv.assign(_src=1)) if len(f)], ignore_index=True)   # empty frames have object dtypes
    value = both.rain_15min_mm.where(both.kind == "rf", both.wl_m)
    both = both.assign(_nan=value.isna()).sort_values(["_nan", "_src"], kind="stable")      # valid first, archive before live
    both = both.drop_duplicates(["graph_id", "kind", "time_local"], keep="first").drop(columns=["_src", "_nan"])
    both = both.sort_values(["graph_id", "time_local"], kind="stable")[COLUMNS]
    out, _ = qc.clean_readings(both, stations=stations if stations is not None else stations_mod.load_default())  # on the full span, then cut
    return out[out.time_local >= first_live].reset_index(drop=True)
