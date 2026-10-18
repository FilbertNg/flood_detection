"""Township Outlook, 6-24 h ahead (build plan E8).

A Watch-level `outlook` alert (horizon 'outlook', confidence 'medium' are set by the caller) when
- an active MET land thunderstorm / heavy-rain warning names the township's state (whole state) or its district, or
- the forecast rain summed over now+6 h .. now+24 h reaches `outlook.forecast_6_24h_min_mm` (config/rules.yaml).

The alert is per township: `street_id` carries the township id and the runner copies it to the streets.
The outlook never raises a street's nowcast level and is never a Warning or Danger.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from .. import met_parse
from .types import Alert, Level, Reason

FROM_H, TO_H = 6, 24
PEAK_FRACTION = 0.5          # window = the run of hours around the peak with at least this share of the peak hour's rain
CAVEAT_EN = "Forecasts often miss tropical storms, so keep watching the live alerts."
CAVEAT_MS = "Ramalan sering terlepas pandang ribut tropika, jadi terus pantau amaran semasa."


def _threshold(cfg: dict) -> float:
    return float(cfg.get("outlook", {}).get("forecast_6_24h_min_mm", 40))


def _band(forecast: pd.DataFrame, now: datetime) -> pd.DataFrame:
    if forecast is None or not len(forecast):
        return pd.DataFrame(columns=["time_local", "precip_mm"])
    f = forecast[["time_local", "precip_mm"]].dropna().copy()
    f["time_local"] = pd.to_datetime(f["time_local"])
    f = f[(f.time_local >= pd.Timestamp(now + timedelta(hours=FROM_H))) & (f.time_local <= pd.Timestamp(now + timedelta(hours=TO_H)))]
    return f.sort_values("time_local").reset_index(drop=True)


def _peak_window(band: pd.DataFrame) -> tuple[datetime, datetime]:
    """Contiguous hourly run around the wettest hour; each row covers [t, t+1 h)."""
    peak = int(band.precip_mm.idxmax())
    floor = band.precip_mm[peak] * PEAK_FRACTION
    one_h = pd.Timedelta(hours=1)
    lo = hi = peak
    while lo > 0 and band.time_local[lo] - band.time_local[lo - 1] == one_h and band.precip_mm[lo - 1] >= floor:
        lo -= 1
    while hi < len(band) - 1 and band.time_local[hi + 1] - band.time_local[hi] == one_h and band.precip_mm[hi + 1] >= floor:
        hi += 1
    return band.time_local[lo].to_pydatetime(), (band.time_local[hi] + one_h).to_pydatetime()


def township_outlook(met_warnings: list[dict], forecast: pd.DataFrame, now: datetime, cfg: dict) -> Alert | None:
    """`met_warnings`: `met_parse.parse_warnings` output; `forecast`: hourly `time_local, precip_mm`;
    `cfg`: the rules config plus `township` {id, district, state}."""
    town = cfg["township"]
    state, district = town.get("state", "Selangor"), town.get("district")
    horizon_end = now + timedelta(hours=TO_H)
    named = [w for w in met_warnings
             if met_parse.overlaps(w, now, horizon_end) and met_parse.names_area(w, state, district)]
    band = _band(forecast, now)
    total = float(band.precip_mm.sum()) if len(band) else 0.0
    rainy = total >= _threshold(cfg)
    if not named and not rainy:
        return None

    reasons: list[Reason] = []
    window: tuple[datetime, datetime] | None = None
    if named:
        w = named[0]
        until = w["valid_to"]
        hours = round((until - now).total_seconds() / 3600, 1) if until else 0.0
        reasons.append(Reason(
            "met_warning", max(hours, 0.0), "h", None,
            f"MET Malaysia has an active '{w['title_en']}' naming {state if not w['areas'].get(state) else district}. {CAVEAT_EN}",
            f"MET Malaysia mengeluarkan '{w['title_ms']}' yang menyebut {state if not w['areas'].get(state) else district}. {CAVEAT_MS}"))
        window = (max(now, w["valid_from"] or now), min(until or horizon_end, horizon_end))
    if rainy:
        start, end = _peak_window(band)
        reasons.append(Reason(
            "forecast_rain", round(total, 1), "mm", None,
            f"The forecast shows {total:.0f} mm of rain in 6 to 24 hours, heaviest {start:%H:%M} to {end:%H:%M}. {CAVEAT_EN}",
            f"Ramalan menunjukkan {total:.0f} mm hujan dalam 6 hingga 24 jam, paling lebat {start:%H:%M} hingga {end:%H:%M}. {CAVEAT_MS}"))
        window = (start, end)
    return Alert(street_id=town["id"], level=Level.WATCH, kind="alert", issued_at=now,
                 window_start=window[0], window_end=window[1], reasons=tuple(reasons), fired_by=("outlook",))


def issue_outlook(candidate: Alert | None, last: Alert | None, now: datetime, cfg: dict) -> Alert | None:
    """Cooldown and all-clear for the township outlook (same `alerts.cooldown_min` as the nowcast).

    `last` = the township's most recent outlook row (alert or all_clear). While an outlook is active nothing is repeated;
    when the condition ends one all-clear is issued; a new outlook within the cooldown of the last row is held back."""
    active = last is not None and last.kind == "alert"
    if candidate is None:
        if not active:
            return None
        return Alert(street_id=last.street_id, level=Level.NORMAL, kind="all_clear", issued_at=now,
                     window_start=None, window_end=None, reasons=(), fired_by=())
    if active:
        return None
    cooldown = timedelta(minutes=cfg["alerts"]["cooldown_min"])
    if last is not None and now - last.issued_at < cooldown:
        return None
    return candidate


def load_forecast(root, point_id: str, model: str = "best_match") -> pd.DataFrame:
    """The latest Open-Meteo fetch for the township point from `<root>/*.parquet` (hourly `time_local, precip_mm`)."""
    from pathlib import Path
    files = sorted(Path(root).glob("*.parquet"))
    empty = pd.DataFrame(columns=["time_local", "precip_mm"])
    if not files:
        return empty
    f = pd.read_parquet(files[-1])
    f = f[(f.point_id == point_id) & (f.model == model)]
    if f.empty:
        return empty
    return f[f.fetched_at_local == f.fetched_at_local.max()][["time_local", "precip_mm"]].reset_index(drop=True)
