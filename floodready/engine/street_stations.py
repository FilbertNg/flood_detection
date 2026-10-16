"""Street -> stations mapping: which river station and rain gauges decide each street's trigger.

File format (assets/geo/<township>_street_stations.json, built by scripts/build_street_stations.py):
  {street_id: {"wl": graph_id | null, "rf": [graph_id, ...], "method": "flow" | "nearest" | null, "distance_m": float | null}}
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


def pick_wl(flow_hits: list[tuple[str, float]], wl_stations: list[tuple[str, float, float]],
            lat: float, lon: float, cfg: dict | None = None) -> tuple[str | None, str | None, float | None]:
    """River station for a street: first one on its flow path within 15 km ("flow"); else the nearest river
    station within `river_radius_km` straight-line ("nearest"); else none. `flow_hits`: (station, metres along the path), nearest first."""
    allowed = {gid for gid, _, _ in wl_stations}
    for gid, along in flow_hits:
        if gid in allowed and along <= FLOW_MAX_M:
            return gid, "flow", float(along)
    if wl_stations:
        d, gid = min((distance_m(lat, lon, wlat, wlon), g) for g, wlat, wlon in wl_stations)
        if d <= (DEFAULTS | (cfg or {}))["river_radius_km"] * 1000:
            return gid, "nearest", round(d, 1)
    return None, None, None


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
    return tuple(([entry["wl"]] if entry.get("wl") else []) + list(entry.get("rf", [])))


def wl_for(mapping: dict | None, street_id: str) -> str | None:
    entry = (mapping or {}).get(street_id)
    return entry.get("wl") if entry else None
