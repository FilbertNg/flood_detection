"""Station rules: the safety floor under the ML trigger (build plan task E3).

Thresholds come from config/rules.yaml (JPS's own figures). The township
trigger is the highest level over its named stations; reasons are ranked by
level, then by how far each value is past its threshold.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from .types import Level, Reason, TriggerResult

_BAND_LEVEL_KEY = ("alert", "warning", "danger")
_BAND_MS = {"alert": "waspada", "warning": "amaran", "danger": "bahaya"}


def _num(x: float) -> str:
    return f"{x:g}"


def rain_level(row: pd.Series, cfg: dict) -> tuple[Level, Reason | None, float]:
    """Level for one rain station, its reason, and the threshold ratio used for ranking."""
    watch, warning = cfg["rain"]["watch"], cfg["rain"]["warning"]
    one_h, span = row.get("st_rain_1h"), row.get("st_rain_2to4h_max")
    one_h = 0.0 if pd.isna(one_h) else float(one_h)
    span = 0.0 if pd.isna(span) else float(span)
    candidates = []  # (level, ratio, code, value)
    if one_h > warning["rain_1h_above_mm"]:
        candidates.append((Level.WARNING, one_h / warning["rain_1h_above_mm"], "rain_1h", one_h))
    if span >= warning["rain_2to4h_min_mm"]:
        candidates.append((Level.WARNING, span / warning["rain_2to4h_min_mm"], "rain_2to4h", span))
    if one_h >= watch["rain_1h_min_mm"]:
        candidates.append((Level.WATCH, one_h / watch["rain_1h_min_mm"], "rain_1h", one_h))
    if span >= watch["rain_2to4h_min_mm"]:
        candidates.append((Level.WATCH, span / watch["rain_2to4h_min_mm"], "rain_2to4h", span))
    if not candidates:
        return Level.NORMAL, None, 0.0
    level, ratio, code, value = max(candidates, key=lambda c: (c[0], c[1]))
    name = row["name"]
    if code == "rain_1h":
        text_en, text_ms = f"{_num(value)} mm of rain in 1 h at {name}", f"Hujan {_num(value)} mm dalam 1 jam di {name}"
    else:
        text_en, text_ms = (f"{_num(value)} mm of rain in the last 2–4 h at {name}",
                            f"Hujan {_num(value)} mm dalam 2–4 jam lepas di {name}")
    return level, Reason(code=code, value=value, unit="mm", station=name, text_en=text_en, text_ms=text_ms), ratio


def river_level(row: pd.Series, cfg: dict, thresholds: dict) -> tuple[Level, Reason | None, float]:
    band = row.get("river_band")
    if band not in _BAND_LEVEL_KEY:
        return Level.NORMAL, None, 0.0
    level = Level.parse(cfg["river"][band])
    value, threshold, name = float(row["wl_m"]), float(thresholds[band]), row["name"]
    reason = Reason(code="river_level", value=value, unit="m", station=name,
                    text_en=f"River at {name} is {value:.2f} m, above its {band} level ({threshold:.2f} m)",
                    text_ms=f"Paras sungai di {name} {value:.2f} m, melepasi paras {_BAND_MS[band]} ({threshold:.2f} m)")
    return level, reason, value / threshold if threshold else 0.0


def township_trigger(features: pd.DataFrame, station_ids: list[str], cfg: dict) -> TriggerResult:
    """Highest rule level over the township's stations (build plan §4.4)."""
    rows = features[features.graph_id.isin(station_ids)]
    data_time = rows.time_local.max() if len(rows) else pd.NaT
    live = rows[~rows.is_stale.astype(bool)]
    reporting = set(live.graph_id)
    stale = tuple(sorted(set(station_ids) - reporting))

    scored = []  # (level, source, ratio, reason)
    for _, row in live.iterrows():
        if row.kind == "rf":
            level, reason, ratio = rain_level(row, cfg)
            source = "rule_rain"
        else:
            th = {"alert": row.get("wl_alert_m"), "warning": row.get("wl_warning_m"), "danger": row.get("wl_danger_m")}
            level, reason, ratio = river_level(row, cfg, th)
            source = "rule_river"
        if reason is not None:
            scored.append((level, source, ratio, reason))

    level = max((s[0] for s in scored), default=Level.NORMAL)
    fired_by = tuple(sorted({s[1] for s in scored if s[0] == level and level > Level.NORMAL},
                            key=["rule_rain", "rule_river"].index))
    reasons = [s[3] for s in sorted(scored, key=lambda s: (s[0], s[2]), reverse=True)]
    if not reporting:
        n = len(station_ids)
        text_en = f"No recent data from {n} of {n} stations" if n else "No stations assigned to this street"
        text_ms = f"Tiada data terkini daripada {n} daripada {n} stesen" if n else "Tiada stesen ditetapkan untuk jalan ini"
        reasons.insert(0, Reason(code="stale_data", value=float(n), unit="stations", station=None,
                                 text_en=text_en, text_ms=text_ms))
    confidence = "low" if not reporting else "high"
    return TriggerResult(level=level, confidence=confidence, fired_by=fired_by, reasons=tuple(reasons),
                         data_time=data_time.to_pydatetime() if pd.notna(data_time) else datetime.min,
                         stale_stations=stale)

