"""Logger and archive jobs (Training Data Spec tasks T2-T4).

Each job runs once and returns a summary; scheduling lives in
scripts/run_loggers.py. Raw responses are always saved before parsing.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from . import infobanjir as ib
from . import met, openmeteo, storage, tide
from .http import fetch_text

log = logging.getLogger(__name__)
MYT = timezone(timedelta(hours=8))


def now_myt() -> datetime:
    return datetime.now(MYT).replace(tzinfo=None)


def _stamp(now_local: datetime) -> dict:
    return {
        "fetched_at_local": now_local,
        "fetched_at_utc": (now_local - timedelta(hours=8)),
    }


# ---------- T2: JPS Infobanjir live tables ----------

def run_jps_live(session, root: Path, states: list[str], now_local: datetime,
                 stale_after: timedelta = timedelta(hours=2)) -> dict:
    root = Path(root) / "jps_live"
    day, hhmm = now_local.strftime("%Y-%m-%d"), now_local.strftime("%H%M")
    summary = {"run_at_local": now_local.isoformat(), "wl_rows": 0, "rf_rows": 0,
               "wl_stale": 0, "rf_stale": 0, "errors": []}
    sources = {
        "wl": (ib.WL_LIVE_URL, ib.wl_live_params, ib.parse_wl_live),
        "rf": (ib.RF_LIVE_URL, ib.rf_live_params, ib.parse_rf_live),
    }
    for state in states:
        for kind, (url, params, parse) in sources.items():
            try:
                page = fetch_text(session, url, params(state))
                storage.save_raw(root / "html" / day / f"{state}_{kind}_{hhmm}.html.gz", page)
                rows = parse(page, state=state)
            except Exception as exc:  # one failing table must not stop the others
                log.exception("JPS live %s %s failed", state, kind)
                summary["errors"].append(f"{state} {kind}: {exc}")
                continue
            if not rows:
                summary["errors"].append(f"{state} {kind}: no rows parsed")
                continue
            df = pd.DataFrame(rows)
            if "daily_mm" in df:
                df["daily_mm"] = df["daily_mm"].map(json.dumps)
            df["is_stale"] = [ib.is_stale(t, now_local, stale_after) for t in df["source_time"]]
            for key, value in _stamp(now_local).items():
                df[key] = value
            storage.append_parquet(df, root / kind / f"{day}.parquet",
                                   keys=["state", "graph_id", "station_code", "source_time"], keep="last")
            summary[f"{kind}_rows"] += len(df)
            summary[f"{kind}_stale"] += int(df["is_stale"].sum())

    total = summary["wl_rows"] + summary["rf_rows"]
    stale = summary["wl_stale"] + summary["rf_stale"]
    summary["ok"] = bool(total) and not summary["errors"] and stale < 0.5 * total
    root.mkdir(parents=True, exist_ok=True)
    (root / "_status.json").write_text(json.dumps(summary, indent=2))
    if not summary["ok"]:
        log.warning("JPS live NOT OK: %s", summary)
    return summary


def rebuild_live_day(root: Path, day: str) -> dict:
    """Re-parse one day's saved live pages (fetch order, latest copy wins) into fresh parquet files.
    Used after a parsing or de-duplication fix; nothing is downloaded."""
    root = Path(root) / "jps_live"
    parsers = {"wl": ib.parse_wl_live, "rf": ib.parse_rf_live}
    counts = {}
    for kind, parse in parsers.items():
        frames = []
        for page in sorted((root / "html" / day).glob(f"*_{kind}_*.html.gz"), key=lambda p: p.name.split("_")[-1]):
            state, hhmm = page.name.split("_")[0], page.name.split("_")[-1][:4]
            rows = parse(storage.read_raw(page), state=state)
            if not rows:
                continue
            df = pd.DataFrame(rows)
            if "daily_mm" in df:
                df["daily_mm"] = df["daily_mm"].map(json.dumps)
            fetched = datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H%M")
            df["is_stale"] = [ib.is_stale(t, fetched) for t in df["source_time"]]
            for key, value in _stamp(fetched).items():
                df[key] = value
            frames.append(df)
        out = root / kind / f"{day}.parquet"
        if frames:
            merged = pd.concat(frames, ignore_index=True).drop_duplicates(
                ["state", "graph_id", "station_code", "source_time"], keep="last")
            out.parent.mkdir(parents=True, exist_ok=True)
            merged.to_parquet(out, index=False)
            counts[kind] = merged.graph_id.nunique()
    return counts


# ---------- T3: MET warnings and Open-Meteo forecasts ----------

def run_met_warnings(session, root: Path, now_local: datetime) -> dict:
    root = Path(root) / "met_warnings"
    day, hhmm = now_local.strftime("%Y-%m-%d"), now_local.strftime("%H%M")
    text = fetch_text(session, met.WARNING_URL)
    storage.save_raw(root / "json" / day / f"{hhmm}.json.gz", text)
    rows = met.flatten_warnings(json.loads(text))
    if rows:
        df = pd.DataFrame(rows)
        for key, value in _stamp(now_local).items():
            df[key] = value
        storage.append_parquet(df, root / f"{day}.parquet",
                               keys=["issued", "title_en", "valid_from", "heading_en"])
    return {"warnings": len(rows)}


def run_forecast(session, root: Path, points: list[dict], models: list[str],
                 now_local: datetime) -> dict:
    root = Path(root) / "openmeteo_live"
    day, hhmm = now_local.strftime("%Y-%m-%d"), now_local.strftime("%H%M")
    text = fetch_text(session, openmeteo.FORECAST_URL, openmeteo.forecast_params(points, models))
    storage.save_raw(root / "json" / day / f"{hhmm}.json.gz", text)
    rows = openmeteo.flatten_forecast(json.loads(text), [p["id"] for p in points], models)
    df = pd.DataFrame(rows)
    for key, value in _stamp(now_local).items():
        df[key] = value
    storage.append_parquet(df, root / f"{day}.parquet",
                           keys=["fetched_at_local", "point_id", "model", "time_local"])
    return {"rows": len(df)}


# ---------- T4: JPS station history archive ----------

_HISTORY = {
    "wl": (ib.WL_HIST_URL, ib.wl_history_rows),
    "rf": (ib.RF_HIST_URL, ib.rf_history_rows),
}


def archive_station_history(session, root: Path, graph_id: str, kind: str,
                            start: date, end: date, pause_s: float = 3.0) -> dict:
    """Download one station's history in monthly chunks. Each chunk's raw
    response is cached, so re-runs only fetch what is missing."""
    url, to_rows = _HISTORY[kind]
    root = Path(root) / "jps_hist"
    summary = {"graph_id": graph_id, "kind": kind, "fetched": 0, "cached": 0, "rows": 0, "failed": []}
    for chunk_from, chunk_to in ib.month_chunks(start, end):
        tag = (datetime.strptime(chunk_from[:10], "%d/%m/%Y").strftime("%Y%m%d") + "_"
               + datetime.strptime(chunk_to[:10], "%d/%m/%Y").strftime("%Y%m%d"))
        raw_path = root / "raw" / kind / graph_id / f"{tag}.json.gz"
        if raw_path.exists():
            summary["cached"] += 1
            continue
        params = {"station": graph_id, "from": chunk_from, "to": chunk_to, "datafreq": 15}
        try:
            text = fetch_text(session, url, params)
            rows = to_rows(ib.parse_history(text), graph_id=graph_id)
        except Exception as exc:
            log.warning("history %s %s %s failed: %s", kind, graph_id, tag, exc)
            summary["failed"].append(tag)
            continue
        finally:
            if pause_s:
                time.sleep(pause_s)
        if rows:
            storage.append_parquet(pd.DataFrame(rows), root / kind / f"{graph_id}.parquet",
                                   keys=["graph_id", "time_local"])
        storage.save_raw(raw_path, text)  # only after a successful parse
        summary["fetched"] += 1
        summary["rows"] += len(rows)
    return summary


def rebuild_history_parquet(root: Path, kind: str, graph_id: str) -> int:
    """Re-parse every cached raw chunk of one station into a fresh parquet
    file (used after a parser fix; nothing is downloaded). Returns row count."""
    _, to_rows = _HISTORY[kind]
    root = Path(root) / "jps_hist"
    rows = []
    for raw_path in sorted((root / "raw" / kind / graph_id).glob("*.json.gz")):
        rows += to_rows(ib.parse_history(storage.read_raw(raw_path)), graph_id=graph_id)
    out = root / kind / f"{graph_id}.parquet"
    if out.exists():
        out.unlink()
    if rows:
        storage.append_parquet(pd.DataFrame(rows), out, keys=["graph_id", "time_local"])
    return len(pd.read_parquet(out)) if rows else 0


def select_archive_stations(wl_rows: list[dict], rf_rows: list[dict],
                            townships: list[dict], districts: list[str]) -> list[tuple[str, str]]:
    """Archive order: township stations first, then stations by district priority."""
    present = {"rf": {r["graph_id"] for r in rf_rows}, "wl": {r["graph_id"] for r in wl_rows}}
    order: list[tuple[str, str]] = []

    def add(graph_id, kind):
        if graph_id in present[kind] and (graph_id, kind) not in order:
            order.append((graph_id, kind))

    for township in townships:
        for station in township.get("stations", []):
            for kind in ("rf", "wl"):
                add(station["graph_id"], kind)
    for district in districts:
        for kind, rows in (("rf", rf_rows), ("wl", wl_rows)):
            for row in rows:
                if row.get("district") == district:
                    add(row["graph_id"], kind)
    return order


# ---------- WP8: MET Malaysia radar composite (opt-in, informational) ----------

def run_radar(session, root: Path, now_local: datetime) -> dict:
    """Archive the newest radar frame to <root>/radar/YYYY-MM-DD/HHMM.gif (MYT of Last-Modified).

    Conditional GET (ETag), so polling every few minutes costs a 304 until MET publishes a new
    frame (about every 10 minutes). The image is checked for the composite layout before saving."""
    from email.utils import parsedate_to_datetime

    from . import radar

    root = Path(root) / "radar"
    root.mkdir(parents=True, exist_ok=True)
    state_file = root / "_state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    summary = {"run_at_local": now_local.isoformat(), "new_frame": False, "errors": [], "ok": False}
    headers = {"If-None-Match": state["etag"]} if state.get("etag") else {}
    try:
        response = session.get(radar.RADAR_URL, timeout=60, headers=headers)
        if response.status_code == 304:
            summary["ok"] = True
        else:
            response.raise_for_status()
            img = radar.read_image(response.content)
            if not radar.is_radar_frame(img):
                raise ValueError("image does not look like the MET radar composite (layout changed?)")
            stamp = response.headers.get("Last-Modified")
            when = (parsedate_to_datetime(stamp).replace(tzinfo=None) + timedelta(hours=8)) if stamp else now_local
            when = when.replace(second=0, microsecond=0)
            path = radar.frame_path(root, when)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(response.content)
                summary["new_frame"] = True
            summary["frame_time"] = when.isoformat()
            if response.headers.get("ETag"):
                state["etag"] = response.headers["ETag"]
                state_file.write_text(json.dumps(state))
            summary["ok"] = True
    except Exception as exc:  # a failed poll must not stop the other loggers
        log.exception("radar failed")
        summary["errors"].append(str(exc))
    (root / "_status.json").write_text(json.dumps(summary, indent=2))
    return summary

# ---------- G3: daily tide refresh ----------

def tide_refresh_due(out_path: Path, now_local: datetime, last_attempt: datetime | None = None,
                     retry_after: timedelta = timedelta(hours=6)) -> bool:
    """True when the tide table is missing or was last written on an earlier day, and the last attempt
    (if any) is at least `retry_after` ago, so a failing download is not hammered."""
    out_path = Path(out_path)
    if last_attempt is not None and now_local - last_attempt < retry_after:
        return False
    if not out_path.exists():
        return True
    return datetime.fromtimestamp(out_path.stat().st_mtime).date() != now_local.date()


def run_tide_refresh(session, raw_dir: Path, out_path: Path, today: date) -> dict:
    """Download this year's Open-Meteo marine sea level up to today + 3 days (one request), cache the raw
    response, and rebuild the hourly table the API and the ML features read."""
    end = today + timedelta(days=3)
    start = date(today.year, 1, 1)
    text = fetch_text(session, tide.MARINE_URL, tide.marine_params(start.isoformat(), end.isoformat()))
    storage.save_raw(Path(raw_dir) / f"{start:%Y%m%d}_{end:%Y%m%d}.json.gz", text)
    table = tide.build_hourly_table(raw_dir, out_path)
    return {"rows": len(table), "last_hour": str(table.time_local.max())}
