"""Radar nowcast from the MET Malaysia Peninsular composite (improvement #16, WP8).

INFORMATIONAL ONLY. Nothing here feeds alert levels: there is no radar history to evaluate it
against yet (docs/radar-nowcast.md). The product is one optional `radar_approaching` Reason.

Source image (a single non-animated GIF, 826x640, refreshed about every 10 minutes):
  https://www.met.gov.my/data/radar_peninsular.gif
  CAPPI composite, azimuthal equidistant projection, 518 km range, rain rate in mm/h drawn with
  the 17-colour legend printed on the right of the image (x >= 570). Times are MYT.
MET Malaysia's copyright notice forbids copying or redistributing site content without written
consent, so the logger is opt-in (config/sources.yaml `radar.enabled`) and frames are never committed.

Georeferencing was fitted, not published: the land/sea mask of the image was matched against
Natural Earth 10 m land (3.6 % of land/sea pixels disagree). Fitted centre pixel (284.5, 319.5)
= 3.8403 N, 101.6072 E, 1.8093 km per pixel; the Kuala Lumpur boundary polygon in the image
lands within 2 px (~4 km) of the real position.
"""
from __future__ import annotations

import io
import logging
import math
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from .engine.types import Reason

log = logging.getLogger(__name__)
RADAR_URL ="https://www.met.gov.my/data/radar_peninsular.gif"

IMG_W, IMG_H = 826, 640
MAP_W = 570                       # map occupies x < 570; the legend sits to the right
CENTRE_LAT, CENTRE_LON = 3.84034, 101.60722
CENTRE_PX = (284.5, 319.5)        # (x, y) array index of the projection centre
KM_PER_PX = 1.8093
EARTH_R_KM = 6371.0

# (colour, lower bound mm/h) from the top of the legend downwards. A pixel is assigned the lower
# bound of its bin, i.e. a deliberately conservative rate (bins are 0.05-0.1, ..., 300-400, >400).
LEGEND: list[tuple[tuple[int, int, int], float]] = [
    ((210, 10, 210), 400.0), ((255, 55, 255), 300.0), ((255, 115, 255), 200.0), ((180, 0, 0), 100.0),
    ((220, 0, 0), 80.0), ((255, 38, 0), 50.0), ((247, 119, 0), 20.0), ((247, 165, 0), 10.0),
    ((255, 209, 0), 8.0), ((255, 255, 0), 5.0), ((0, 240, 0), 2.0), ((0, 200, 0), 1.0),
    ((0, 172, 0), 0.8), ((0, 135, 0), 0.5), ((52, 206, 236), 0.2), ((5, 155, 255), 0.1),
    ((0, 113, 226), 0.05),
]
SWATCH_ROWS = [(77, 93), (94, 109), (110, 126), (127, 142), (143, 158), (159, 175), (176, 191), (192, 207),
               (208, 224), (225, 240), (241, 257), (258, 273), (274, 289), (290, 306), (307, 322),
               (323, 338), (339, 355)]
SWATCH_X = 620
COLOUR_TOL_SQ = 300               # squared RGB distance tolerated after GIF quantisation

RINGS_KM = (10, 25, 50)

# nowcast tuning (conservative: say nothing unless sure)
CELL_MIN_MM_H = 5.0               # a "rain cell" is a connected echo >= 5 mm/h ...
CELL_MIN_PX = 4                   # ... of at least 4 pixels (~13 km2)
SEARCH_KM = 80.0
OVERHEAD_KM = 3.0                 # already over the township: nothing to announce
MIN_APPROACH_KMH = 8.0
MAX_MISS_KM = 12.0                # cross-track distance between the cell's track and the township
MAX_ETA_MIN = 90.0
MAX_SPEED_KMH = 120.0
MIN_PEAK = 0.15                   # phase-correlation peak (0..1) needed to trust the motion
MIN_ECHO_PX = 30                  # echo pixels (>= 0.5 mm/h) needed in both windows
WINDOW_PX = 128                   # motion window around the township (+-116 km)
MAX_FRAME_AGE_MIN = 25
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
COMPASS_MS = ["utara", "timur laut", "timur", "tenggara", "selatan", "barat daya", "barat", "barat laut"]


# ---------- georeferencing (spherical azimuthal equidistant) ----------

def _forward_km(lat, lon):
    """(east_km, north_km) of a point in the projection centred on the fitted centre."""
    p1, l1 = math.radians(CENTRE_LAT), math.radians(CENTRE_LON)
    p2, l2 = np.radians(lat), np.radians(lon)
    dl = l2 - l1
    cosc = math.sin(p1) * np.sin(p2) + math.cos(p1) * np.cos(p2) * np.cos(dl)
    c = np.arccos(np.clip(cosc, -1, 1))
    az_x = np.cos(p2) * np.sin(dl)
    az_y = math.cos(p1) * np.sin(p2) - math.sin(p1) * np.cos(p2) * np.cos(dl)
    norm = np.hypot(az_x, az_y)
    norm = np.where(norm == 0, 1, norm)
    return EARTH_R_KM * c * az_x / norm, EARTH_R_KM * c * az_y / norm


def _inverse_km(east, north):
    p1, l1 = math.radians(CENTRE_LAT), math.radians(CENTRE_LON)
    rho = np.hypot(east, north)
    c = rho / EARTH_R_KM
    rho_safe = np.where(rho == 0, 1, rho)
    lat = np.arcsin(np.cos(c) * math.sin(p1) + (north * np.sin(c) * math.cos(p1) / rho_safe))
    lon = l1 + np.arctan2(east * np.sin(c), rho_safe * math.cos(p1) * np.cos(c) - north * math.sin(p1) * np.sin(c))
    return np.degrees(lat), np.degrees(lon)


def latlon_to_pixel(lat, lon):
    east, north = _forward_km(lat, lon)
    x, y = CENTRE_PX[0] + east / KM_PER_PX, CENTRE_PX[1] - north / KM_PER_PX
    return (float(x), float(y)) if np.ndim(x) == 0 else (x, y)


def pixel_to_latlon(x, y):
    lat, lon = _inverse_km((np.asarray(x) - CENTRE_PX[0]) * KM_PER_PX, -(np.asarray(y) - CENTRE_PX[1]) * KM_PER_PX)
    return (float(lat), float(lon)) if np.ndim(lat) == 0 else (lat, lon)


def offset_latlon(lat, lon, east_km, north_km):
    """Small-offset helper (flat earth, fine within ~100 km)."""
    return lat + north_km / 111.195, lon + east_km / (111.195 * math.cos(math.radians(lat)))


# ---------- decoding ----------

def read_image(data: bytes) -> np.ndarray:
    from PIL import Image
    return np.array(Image.open(io.BytesIO(data)).convert("RGB"))


def is_radar_frame(img: np.ndarray) -> bool:
    """True when the image has the MET composite layout (checks the legend swatches)."""
    if img.shape != (IMG_H, IMG_W, 3):
        return False
    hits = 0
    for (rgb, _), (y0, y1) in zip(LEGEND, SWATCH_ROWS):
        px = img[(y0 + y1) // 2, SWATCH_X].astype(int)
        hits += int(((px - np.array(rgb)) ** 2).sum() <= COLOUR_TOL_SQ)
    return hits >= 15


def decode_rate(img: np.ndarray) -> np.ndarray:
    """RGB image -> rain rate in mm/h on the map area (H x MAP_W); 0 where there is no echo."""
    area = img[:, :MAP_W].astype(int)
    rate = np.zeros(area.shape[:2], np.float32)
    best = np.full(area.shape[:2], COLOUR_TOL_SQ + 1)
    for rgb, lo in LEGEND:
        d = ((area - np.array(rgb)) ** 2).sum(axis=2)
        hit = (d <= COLOUR_TOL_SQ) & (d < best)
        rate[hit] = lo
        best[hit] = d[hit]
    return rate


def _pixel_distance_km(lat, lon, shape):
    cx, cy = latlon_to_pixel(lat, lon)
    ys, xs = np.mgrid[0:shape[0], 0:shape[1]]
    return np.hypot(xs - cx, ys - cy) * KM_PER_PX, (cx, cy)


def township_stats(rate: np.ndarray, lat: float, lon: float, rings=RINGS_KM) -> dict[int, dict]:
    """Max and areal-mean rain rate (mm/h) within each ring around a township centre."""
    dist, _ = _pixel_distance_km(lat, lon, rate.shape)
    out = {}
    for r in rings:
        sel = rate[dist <= r]
        out[r] = {"max": float(sel.max()) if sel.size else 0.0, "mean": float(sel.mean()) if sel.size else 0.0}
    return out


# ---------- motion ----------

def _phase_correlate(a: np.ndarray, b: np.ndarray):
    """Shift (dy, dx) so that b(x) ~ a(x - shift), and the correlation peak (0..1)."""
    h, w = a.shape
    win = np.outer(np.hanning(h), np.hanning(w))
    fa, fb = np.fft.fft2(a * win), np.fft.fft2(b * win)
    cross = np.conj(fa) * fb
    cross /= np.abs(cross) + 1e-3 * np.abs(cross).max()
    corr = np.fft.ifft2(cross).real
    iy, ix = np.unravel_index(np.argmax(corr), corr.shape)
    peak = float(corr[iy, ix])

    def refine(i, n, line):  # parabolic sub-pixel offset
        l, c, r = line[(i - 1) % n], line[i], line[(i + 1) % n]
        den = l - 2 * c + r
        return 0.0 if den == 0 else 0.5 * (l - r) / den

    dy = iy + refine(iy, h, corr[:, ix])
    dx = ix + refine(ix, w, corr[iy, :])
    dy = dy - h if dy > h / 2 else dy
    dx = dx - w if dx > w / 2 else dx
    return dy, dx, peak


def estimate_motion(prev: np.ndarray, cur: np.ndarray, dt_min: float, centre_latlon) -> dict | None:
    """Echo motion around the township between two frames; None unless confident."""
    cx, cy = latlon_to_pixel(*centre_latlon)
    half = WINDOW_PX // 2
    x0 = int(np.clip(round(cx) - half, 0, cur.shape[1] - WINDOW_PX))
    y0 = int(np.clip(round(cy) - half, 0, cur.shape[0] - WINDOW_PX))
    a = np.sqrt(prev[y0:y0 + WINDOW_PX, x0:x0 + WINDOW_PX])
    b = np.sqrt(cur[y0:y0 + WINDOW_PX, x0:x0 + WINDOW_PX])
    if (a > np.sqrt(0.5)).sum() < MIN_ECHO_PX or (b > np.sqrt(0.5)).sum() < MIN_ECHO_PX or dt_min <= 0:
        return None
    dy, dx, peak = _phase_correlate(a, b)
    hours = dt_min / 60.0
    u, v = dx * KM_PER_PX / hours, -dy * KM_PER_PX / hours   # east, north (image y points south)
    if peak < MIN_PEAK or math.hypot(u, v) > MAX_SPEED_KMH:
        return None
    return {"u_kmh": float(u), "v_kmh": float(v), "speed_kmh": float(math.hypot(u, v)), "confidence": peak}


def _compass(east, north, names=COMPASS):
    return names[int(((math.degrees(math.atan2(east, north)) + 22.5) % 360) // 45)]


def nowcast(prev: np.ndarray, cur: np.ndarray, dt_min: float, lat: float, lon: float) -> dict | None:
    """The nearest rain cell heading for the township, or None when there is no confident answer."""
    motion = estimate_motion(prev, cur, dt_min, (lat, lon))
    if motion is None:
        return None
    from scipy import ndimage

    dist, (cx, cy) = _pixel_distance_km(lat, lon, cur.shape)
    labels, n = ndimage.label(cur >= CELL_MIN_MM_H)
    ys, xs = np.mgrid[0:cur.shape[0], 0:cur.shape[1]]
    u, v = motion["u_kmh"], motion["v_kmh"]
    speed = motion["speed_kmh"]
    best = None
    for i in range(1, n + 1):
        sel = labels == i
        if sel.sum() < CELL_MIN_PX:
            continue
        d = np.where(sel, dist, np.inf)
        j = np.unravel_index(np.argmin(d), d.shape)
        near = float(d[j])
        if near < OVERHEAD_KM or near > SEARCH_KM:
            continue
        # vector cell -> township, km (east, north)
        to_e, to_n = (cx - xs[j]) * KM_PER_PX, -(cy - ys[j]) * KM_PER_PX
        approach = (u * to_e + v * to_n) / near                  # km/h along the line to the township
        miss = abs(u * to_n - v * to_e) / speed                   # cross-track distance, km
        if approach < MIN_APPROACH_KMH or miss > MAX_MISS_KM:
            continue
        eta = near / approach * 60.0
        if eta > MAX_ETA_MIN:
            continue
        if best is None or eta < best["eta_min"]:
            best = {"direction": _compass(-to_e, -to_n), "direction_ms": _compass(-to_e, -to_n, COMPASS_MS),
                    "distance_km": near, "eta_min": float(eta), "speed_kmh": float(speed),
                    "max_mm_h": float(cur[sel].max()), "confidence": motion["confidence"]}
    return best


def to_reason(result: dict) -> Reason:
    """Informational Reason for the API. Never an input to alert levels."""
    km, eta = round(result["distance_km"]), round(result["eta_min"])
    d_ms = result.get("direction_ms") or result["direction"]
    return Reason(
        code="radar_approaching", value=float(eta), unit="min", station=None,
        text_en=f"Radar: rain cell about {km} km to the {result['direction']}, heading this way, "
                f"arriving in about {eta} min (informational; source: MET Malaysia radar).",
        text_ms=f"Radar: sel hujan kira-kira {km} km ke {d_ms}, bergerak ke sini, "
                f"tiba dalam lebih kurang {eta} min (makluman sahaja; sumber: radar MET Malaysia).",
    )


# ---------- archive ----------

_FRAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[\\/](\d{4})\.gif$")


def list_frames(root: Path) -> list[tuple[datetime, Path]]:
    out = []
    for p in Path(root).rglob("*.gif"):
        m = _FRAME_RE.search(str(p))
        if m:
            out.append((datetime.strptime(m.group(1) + m.group(2), "%Y-%m-%d%H%M"), p))
    return sorted(out)


def frame_path(root: Path, when: datetime) -> Path:
    return Path(root) / when.strftime("%Y-%m-%d") / when.strftime("%H%M.gif")


def latest_reason(root: Path, lat: float, lon: float, now: datetime,
                  max_age_min: float = MAX_FRAME_AGE_MIN) -> Reason | None:
    """`radar_approaching` from the two newest archived frames, or None (also when they are stale)."""
    key = (str(root), round(lat, 4), round(lon, 4))
    entry = _CACHE.get(key)
    if entry is None or _monotonic() - entry["checked"] > CACHE_TTL_S:
        frames = list_frames(root)
        sig = tuple((str(p), p.stat().st_mtime_ns) for _, p in frames[-2:])
        if entry is None or entry["sig"] != sig:
            entry = {"sig": sig, "newest": frames[-1][0] if frames else None, "reason": _compute(frames, lat, lon)}
        entry["checked"] = _monotonic()
        _CACHE[key] = entry
    if entry["newest"] is None or now - entry["newest"] > timedelta(minutes=max_age_min):
        return None
    return entry["reason"]


def _compute(frames, lat, lon) -> Reason | None:
    if len(frames) < 2:
        return None
    (t0, p0), (t1, p1) = frames[-2], frames[-1]
    dt = (t1 - t0).total_seconds() / 60
    if not 5 <= dt <= 30:
        return None
    try:
        imgs = [read_image(p.read_bytes()) for p in (p0, p1)]
        if not all(is_radar_frame(i) for i in imgs):
            return None
        result = nowcast(decode_rate(imgs[0]), decode_rate(imgs[1]), dt, lat, lon)
    except Exception as exc:  # corrupt or half-written frame: say nothing, warn once per frame pair
        log.warning("radar frames %s / %s unreadable: %s", p0.name, p1.name, exc)
        return None
    return to_reason(result) if result else None


_CACHE: dict = {}
CACHE_TTL_S = 15.0   # how often the archive directory is rescanned; frames arrive about every 10 min


def _monotonic() -> float:
    return time.monotonic()


def clear_cache() -> None:
    _CACHE.clear()
