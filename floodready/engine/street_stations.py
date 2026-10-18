"""Street -> stations mapping: which river station and rain gauges decide each street's trigger.

File format (assets/geo/<township>_street_stations.json, built by scripts/build_street_stations.py):
  {street_id: {"wl": graph_id | null, "wl_candidates": [graph_id, ...], "rf": [graph_id, ...],
               "method": "flow" | "nearest" | null, "distance_m": float | null}}
`wl` is the first of `wl_candidates` (kept for readers of the old format); the rest are fallbacks used when the
street's own river station is dead or stale (see `wl_for`).
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path

log = logging.getLogger(__name__)

FLOW_MAX_M = 15_000
# Defaults match `street_stations:` in config/rules.yaml (the script passes the config through).
DEFAULTS = {"rain_radius_km": 10, "min_rain_gauges": 2, "river_radius_km": 10}


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def rain_gauges(lat: float, lon: float, gauges: list[tuple[str, float, float]], cfg: dict | None = None) -> list[str]:
    """Gauges within `rain_radius_km` of the point; if fewer than `min_rain_gauges`, the nearest that many. Nearest first."""
    cfg = DEFAULTS | (cfg or {})
    ranked = sorted((distance_m(lat, lon, glat, glon), gid) for gid, glat, glon in gauges)
    near = [gid for d, gid in ranked if d <= cfg["rain_radius_km"] * 1000]
    return near if len(near) >= cfg["min_rain_gauges"] else [gid for _, gid in ranked[:cfg["min_rain_gauges"]]]


def pick_wl_candidates(flow_hits: list[tuple[str, float]], wl_stations: list[tuple[str, float, float]],
                       lat: float, lon: float, cfg: dict | None = None) -> list[tuple[str, str, float]]:
    """Ordered river-station candidates for a street, as (station, method, metres): the stations on its flow path
    within 15 km ("flow", along-path order), then the other river stations within `river_radius_km` straight-line
    ("nearest", nearest first). The first is the street's own station; the rest are fallbacks when it is dead or stale."""
    allowed = {gid for gid, _, _ in wl_stations}
    out: list[tuple[str, str, float]] = []
    for gid, along in flow_hits:
        if gid in allowed and along <= FLOW_MAX_M and gid not in {c[0] for c in out}:
            out.append((gid, "flow", float(along)))
    radius = (DEFAULTS | (cfg or {}))["river_radius_km"] * 1000
    for d, gid in sorted((distance_m(lat, lon, wlat, wlon), g) for g, wlat, wlon in wl_stations):
        if d <= radius and gid not in {c[0] for c in out}:
            out.append((gid, "nearest", round(d, 1)))
    return out


def pick_wl(flow_hits: list[tuple[str, float]], wl_stations: list[tuple[str, float, float]],
            lat: float, lon: float, cfg: dict | None = None) -> tuple[str | None, str | None, float | None]:
    """The street's own river station (the first candidate): on its flow path within 15 km ("flow"), else the
    nearest within `river_radius_km` ("nearest"), else none. `flow_hits`: (station, metres along the path), nearest first."""
    candidates = pick_wl_candidates(flow_hits, wl_stations, lat, lon, cfg)
    return candidates[0] if candidates else (None, None, None)


def load(path: Path) -> dict | None:
    """The mapping, or None (with a warning) when the file is missing or unreadable: the engine then
    falls back to one township-wide trigger."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("No street-stations mapping (%s): using one township-wide trigger for every street", exc)
        return None


def stations_for(mapping: dict | None, street_id: str) -> tuple[str, ...] | None:
    """The street's own station ids, river station first; None if the street is not in the mapping."""
    entry = (mapping or {}).get(street_id)
    if entry is None:
        return None
    return tuple(dict.fromkeys(([entry["wl"]] if entry.get("wl") else []) + list(entry.get("rf", []))))


def candidates_for(mapping: dict | None, street_id: str) -> tuple[str, ...]:
    """The street's river stations in order of preference (own station first); empty when it has none.
    Files written before `wl_candidates` existed are read as `[wl]`."""
    entry = (mapping or {}).get(street_id)
    if not entry:
        return ()
    listed = entry.get("wl_candidates")
    if listed is None:
        listed = [entry["wl"]] if entry.get("wl") else []
    return tuple(dict.fromkeys(listed))


def wl_for(mapping: dict | None, street_id: str, dead_or_stale: set[str] | None = None) -> str | None:
    """The street's river station at a moment: its first candidate that is not in `dead_or_stale`; None when
    it has no candidate or every one is dead or stale."""
    dead = dead_or_stale or set()
    return next((gid for gid in candidates_for(mapping, street_id) if gid not in dead), None)


def dead_wl(features_at_t, ids) -> set[str]:
    """Which of the river stations `ids` are dead or stale at t: no river row in `features_at_t` (the engine's
    features for t, built only from QC-cleaned readings at or before t) or a row flagged `is_stale`, i.e. no valid
    reading in the last `stale_after_min`. Causal: it never looks past t."""
    rows = features_at_t[features_at_t.kind == "wl"] if len(features_at_t) else features_at_t
    live = set(rows.graph_id[~rows.is_stale.astype(bool)]) if len(rows) else set()
    return {gid for gid in ids if gid not in live}
