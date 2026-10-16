from datetime import datetime

import pytest

from floodready import radar
from tests.test_radar import BBR, make_frame, to_gif


@pytest.fixture()
def archive(tmp_path):
    lat, lon = BBR
    day = tmp_path / "radar" / "2026-10-16"
    day.mkdir(parents=True)
    for name, e in (("1511", 46), ("1521", 40)):
        img = make_frame([(*radar.offset_latlon(lat, lon, east_km=e, north_km=0), 4, 25.0)])
        (day / f"{name}.gif").write_bytes(to_gif(img))
    radar.clear_cache()
    return tmp_path / "radar"


def count_nowcasts(monkeypatch):
    calls = []
    real = radar.nowcast
    monkeypatch.setattr(radar, "nowcast", lambda *a, **k: calls.append(1) or real(*a, **k))
    return calls


def test_same_frames_are_not_recomputed(archive, monkeypatch):
    calls = count_nowcasts(monkeypatch)
    now = datetime(2026, 10, 16, 15, 25)
    first = radar.latest_reason(archive, *BBR, now=now)
    second = radar.latest_reason(archive, *BBR, now=now)
    assert first is not None and second == first and len(calls) == 1


def test_a_new_frame_is_picked_up_after_the_ttl(archive, monkeypatch):
    calls = count_nowcasts(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr(radar, "_monotonic", lambda: clock[0])
    now = datetime(2026, 10, 16, 15, 25)
    radar.latest_reason(archive, *BBR, now=now)
    (archive / "2026-10-16" / "1531.gif").write_bytes((archive / "2026-10-16" / "1521.gif").read_bytes())
    radar.latest_reason(archive, *BBR, now=now)           # inside the TTL: no directory scan yet
    assert len(calls) == 1
    clock[0] += radar.CACHE_TTL_S + 1
    radar.latest_reason(archive, *BBR, now=datetime(2026, 10, 16, 15, 35))
    assert len(calls) == 2


def test_staleness_follows_the_clock_passed_in_not_the_cache(archive):
    assert radar.latest_reason(archive, *BBR, now=datetime(2026, 10, 16, 15, 25)) is not None
    assert radar.latest_reason(archive, *BBR, now=datetime(2026, 10, 16, 16, 30)) is None


def test_reason_credits_met_malaysia():
    r = radar.to_reason({"direction": "E", "distance_km": 30.0, "eta_min": 45.0})
    assert "MET Malaysia" in r.text_en and "MET Malaysia" in r.text_ms


def test_corrupt_newest_frame_gives_none_and_one_warning(archive, caplog):
    (archive / "2026-10-16" / "1521.gif").write_bytes(b"GIF89a-not-an-image")
    radar.clear_cache()
    with caplog.at_level("WARNING"):
        assert radar.latest_reason(archive, *BBR, now=datetime(2026, 10, 16, 15, 25)) is None
        assert radar.latest_reason(archive, *BBR, now=datetime(2026, 10, 16, 15, 25)) is None
    assert len([r for r in caplog.records if r.levelname == "WARNING"]) == 1
