"""Radar nowcast tests on synthetic frames that reproduce the MET Malaysia composite layout.

Real MET frames are Malaysian Government copyright (see docs/radar-nowcast.md), so none is committed."""
import io
from datetime import datetime, timedelta

import numpy as np
import pytest
import requests
from PIL import Image

from floodready import jobs, radar

BBR = (3.0852, 101.4377)  # Bandar Bukit Raja (config/townships.yaml)
SEA = (110, 112, 190)


def rate_color(rate):
    """Legend colour of the bin that contains `rate` mm/h."""
    for rgb, lo in radar.LEGEND:
        if rate >= lo:
            return rgb
    raise ValueError(rate)


def make_frame(blobs=()):
    """826x640 composite: sea-coloured map, legend swatches, and square echo blobs
    given as (lat, lon, half_size_px, mm_per_h)."""
    img = np.zeros((radar.IMG_H, radar.IMG_W, 3), np.uint8)
    img[:] = (239, 235, 231)
    img[:, :radar.MAP_W] = SEA
    for (rgb, _), (y0, y1) in zip(radar.LEGEND, radar.SWATCH_ROWS):
        img[y0:y1 + 1, 582:656] = rgb
    for lat, lon, half, rate in blobs:
        x, y = radar.latlon_to_pixel(lat, lon)
        x, y = int(round(x)), int(round(y))
        img[y - half:y + half + 1, x - half:x + half + 1] = rate_color(rate)
    return img


def to_gif(img) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(img).convert("P", palette=Image.ADAPTIVE, colors=64).save(buf, "GIF")
    return buf.getvalue()


def test_georeference_matches_known_landmarks():
    # Verified against Natural Earth land (see docs): KL polygon centre sits at ~(288, 363) px.
    x, y = radar.latlon_to_pixel(3.139, 101.687)
    assert abs(x - 289.4) < 1.0 and abs(y - 362.6) < 1.0
    lat, lon = radar.pixel_to_latlon(x, y)
    assert lat == pytest.approx(3.139, abs=1e-6) and lon == pytest.approx(101.687, abs=1e-6)


def test_decode_rate_uses_legend_lower_bounds():
    img = make_frame([(BBR[0], BBR[1], 2, 12.0), (3.5, 101.0, 2, 0.3), (3.0, 102.0, 1, 450.0)])
    rate = radar.decode_rate(img)
    x, y = (int(round(v)) for v in radar.latlon_to_pixel(*BBR))
    assert rate[y, x] == 10.0           # 12 mm/h is in the 10-20 bin; the bin's lower bound is used
    x2, y2 = (int(round(v)) for v in radar.latlon_to_pixel(3.5, 101.0))
    assert rate[y2, x2] == 0.2
    x3, y3 = (int(round(v)) for v in radar.latlon_to_pixel(3.0, 102.0))
    assert rate[y3, x3] == 400.0
    assert rate[0, 0] == 0.0            # sea background is no echo
    assert rate.shape == (radar.IMG_H, radar.MAP_W)


def test_decode_gif_roundtrip_survives_palette_quantisation():
    img = make_frame([(BBR[0], BBR[1], 3, 30.0)])
    rate = radar.decode_rate(radar.read_image(to_gif(img)))
    assert rate.max() == 20.0
    assert (rate > 0).sum() == 49


def test_township_stats_rings():
    lat, lon = BBR
    # cell of 3 km half-size 20 km east: inside 25 km ring only
    east_lat, east_lon = radar.offset_latlon(lat, lon, east_km=20, north_km=0)
    rate = radar.decode_rate(make_frame([(east_lat, east_lon, 2, 8.0)]))
    stats = radar.township_stats(rate, lat, lon)
    assert stats[10]["max"] == 0.0 and stats[10]["mean"] == 0.0
    assert stats[25]["max"] == 8.0 and stats[50]["max"] == 8.0
    assert 0 < stats[25]["mean"] < stats[25]["max"]
    assert stats[50]["mean"] < stats[25]["mean"]


def moving_pair(east_km, speed_kmh, dt_min=10, toward=True, north_km=0.0):
    """Frames `dt_min` apart with one cell `east_km` east of BBR moving west at speed_kmh."""
    lat, lon = BBR
    step = speed_kmh * dt_min / 60.0
    pos = [(east_km + step, north_km), (east_km, north_km)] if toward else [(east_km - step, north_km), (east_km, north_km)]
    frames = []
    for e, n in pos:
        la, lo = radar.offset_latlon(lat, lon, east_km=e, north_km=n)
        extras = [(*radar.offset_latlon(lat, lon, east_km=e + 30, north_km=n + 25), 2, 5.0)]
        frames.append(radar.decode_rate(make_frame([(la, lo, 4, 25.0)] + [(*radar.offset_latlon(la, lo, east_km=10, north_km=6), 2, 8.0)] + extras)))
    return frames


def test_motion_phase_correlation_recovers_shift():
    prev, cur = moving_pair(40, 36)  # 6 km per 10 min = ~3.3 px, westward
    motion = radar.estimate_motion(prev, cur, dt_min=10, centre_latlon=BBR)
    assert motion is not None
    assert motion["u_kmh"] == pytest.approx(-36, abs=7)
    assert abs(motion["v_kmh"]) < 7
    assert motion["confidence"] >= radar.MIN_PEAK


def test_motion_none_without_echo():
    empty = radar.decode_rate(make_frame())
    assert radar.estimate_motion(empty, empty, dt_min=10, centre_latlon=BBR) is None


def test_approaching_cell_gives_eta():
    prev, cur = moving_pair(40, 36)
    result = radar.nowcast(prev, cur, dt_min=10, lat=BBR[0], lon=BBR[1])
    assert result is not None
    assert result["direction"] == "E"
    assert result["distance_km"] == pytest.approx(33, abs=6)  # nearest echo edge, not the centre
    assert 40 <= result["eta_min"] <= 70
    assert result["max_mm_h"] >= 8


def test_receding_cell_gives_nothing():
    prev, cur = moving_pair(40, 36, toward=False)
    assert radar.nowcast(prev, cur, dt_min=10, lat=BBR[0], lon=BBR[1]) is None


def test_cell_missing_the_township_gives_nothing():
    prev, cur = moving_pair(40, 36, north_km=40)  # passes 40 km north of the township
    assert radar.nowcast(prev, cur, dt_min=10, lat=BBR[0], lon=BBR[1]) is None


def test_stationary_or_slow_cell_gives_nothing():
    prev, cur = moving_pair(40, 0)
    assert radar.nowcast(prev, cur, dt_min=10, lat=BBR[0], lon=BBR[1]) is None


def test_reason_is_informational_radar_approaching():
    reason = radar.to_reason({"direction": "W", "distance_km": 18.0, "eta_min": 30.0, "speed_kmh": 36.0, "max_mm_h": 50.0})
    assert reason.code == "radar_approaching" and reason.unit == "min" and reason.value == 30.0
    assert reason.station is None
    assert "W" in reason.text_en and "30" in reason.text_en
    assert reason.text_ms


# ---------- logger job ----------

class RadarSession:
    """Serves one GIF; honours If-None-Match like the real server (ETag)."""

    def __init__(self, gif, etag='"a"', last_modified="Fri, 16 Oct 2026 07:21:04 GMT"):
        self.gif, self.etag, self.lm, self.calls = gif, etag, last_modified, []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append((url, dict(headers or {})))
        r = requests.Response()
        if (headers or {}).get("If-None-Match") == self.etag:
            r.status_code = 304
            return r
        r.status_code = 200
        r._content = self.gif
        r.headers["ETag"], r.headers["Last-Modified"] = self.etag, self.lm
        return r


def test_run_radar_archives_frame_once(tmp_path):
    gif = to_gif(make_frame([(BBR[0], BBR[1], 2, 8.0)]))
    session = RadarSession(gif)
    now = datetime(2026, 10, 16, 15, 25)
    first = jobs.run_radar(session, tmp_path, now)
    assert first["new_frame"] is True and first["ok"] is True
    saved = tmp_path / "radar" / "2026-10-16" / "1521.gif"  # Last-Modified 07:21 UTC = 15:21 MYT
    assert saved.read_bytes() == gif
    second = jobs.run_radar(session, tmp_path, now + timedelta(minutes=5))
    assert second["new_frame"] is False and second["ok"] is True
    assert session.calls[1][1].get("If-None-Match") == '"a"'
    assert len(list((tmp_path / "radar").rglob("*.gif"))) == 1


def test_run_radar_rejects_non_radar_image(tmp_path):
    junk = to_gif(np.zeros((100, 100, 3), np.uint8))
    summary = jobs.run_radar(RadarSession(junk), tmp_path, datetime(2026, 10, 16, 15, 25))
    assert summary["ok"] is False and not list((tmp_path / "radar").rglob("*.gif"))


def test_latest_reason_reads_archive(tmp_path):
    lat, lon = BBR
    prev_img, cur_img = (make_frame([(*radar.offset_latlon(lat, lon, east_km=e, north_km=0), 4, 25.0)]) for e in (46, 40))
    day = tmp_path / "radar" / "2026-10-16"
    day.mkdir(parents=True)
    (day / "1511.gif").write_bytes(to_gif(prev_img))
    (day / "1521.gif").write_bytes(to_gif(cur_img))
    reason = radar.latest_reason(tmp_path / "radar", lat, lon, now=datetime(2026, 10, 16, 15, 25))
    assert reason is not None and reason.code == "radar_approaching"
    # stale archive (newest frame > 25 min old) says nothing
    assert radar.latest_reason(tmp_path / "radar", lat, lon, now=datetime(2026, 10, 16, 16, 30)) is None
