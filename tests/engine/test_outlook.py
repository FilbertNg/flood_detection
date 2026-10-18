import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from floodready import met_parse
from floodready.engine import outlook
from floodready.engine.types import Level

FIX = Path(__file__).resolve().parents[1] / "fixtures"
NOW = datetime(2026, 10, 16, 16, 0)          # inside the saved warning's 15:00-20:00 validity


@pytest.fixture
def cfg(rules_cfg):
    return {**rules_cfg, "township": {"id": "BBR", "district": "Klang", "state": "Selangor"}}


def warnings(name):
    return met_parse.parse_warnings(json.loads((FIX / name).read_text(encoding="utf-8")))


def hourly(now, offsets_mm):
    """Hourly forecast rows `now + offset hours -> mm`."""
    return pd.DataFrame({"time_local": [now + timedelta(hours=h) for h in offsets_mm], "precip_mm": list(offsets_mm.values())})


QUIET = {h: 0.2 for h in range(1, 25)}


def test_met_warning_naming_selangor_is_an_active_watch(cfg):
    a = outlook.township_outlook(warnings("met_thunderstorm_klang_listed.json"), hourly(NOW, QUIET), NOW, cfg)
    assert a is not None and a.level is Level.WATCH and a.kind == "alert" and a.fired_by == ("outlook",)
    assert a.street_id == "BBR" and a.issued_at == NOW
    assert a.reasons[0].code == "met_warning" and "Thunderstorms Warning" in a.reasons[0].text_en
    assert "Amaran Ribut Petir" in a.reasons[0].text_ms


def test_bare_selangor_also_counts(cfg):
    now = datetime(2026, 10, 17, 15, 30)
    assert outlook.township_outlook(warnings("met_thunderstorm_selangor_bare.json"), hourly(now, {}), now, cfg) is not None


def test_selangor_named_without_klang_is_not_enough(cfg):
    now = datetime(2026, 10, 16, 21, 30)
    assert outlook.township_outlook(warnings("met_thunderstorm_selangor_other_districts.json"), hourly(now, {}), now, cfg) is None


def test_forecast_45mm_gives_window_18_to_21(cfg):
    now = datetime(2026, 10, 16, 12, 0)                       # 18:00 is +6 h
    fc = pd.DataFrame({"time_local": [datetime(2026, 10, 16, h) for h in (17, 18, 19, 20, 21)],
                       "precip_mm": [0.0, 15.0, 15.0, 15.0, 0.0]})
    a = outlook.township_outlook([], fc, now, cfg)
    assert a is not None and a.level is Level.WATCH
    assert (a.window_start, a.window_end) == (datetime(2026, 10, 16, 18), datetime(2026, 10, 16, 21))
    r = a.reasons[0]
    assert r.code == "forecast_rain" and r.value == 45.0 and r.unit == "mm"
    assert "45" in r.text_en and "45" in r.text_ms


def test_five_mm_and_no_warning_gives_none(cfg):
    now = datetime(2026, 10, 16, 12, 0)
    fc = pd.DataFrame({"time_local": [datetime(2026, 10, 16, 19), datetime(2026, 10, 16, 20)], "precip_mm": [2.5, 2.5]})
    assert outlook.township_outlook([], fc, now, cfg) is None
    assert outlook.township_outlook([], pd.DataFrame(columns=["time_local", "precip_mm"]), now, cfg) is None


def test_only_the_6_to_24h_band_counts(cfg):
    now = datetime(2026, 10, 16, 12, 0)
    fc = hourly(now, {2: 30.0, 3: 30.0, 5: 30.0, 25: 30.0, 26: 30.0})
    assert outlook.township_outlook([], fc, now, cfg) is None


def test_threshold_is_the_configured_one(cfg):
    now = datetime(2026, 10, 16, 12, 0)
    fc = hourly(now, {8: 40.0})
    assert outlook.township_outlook([], fc, now, cfg) is not None
    cfg["outlook"] = {"forecast_6_24h_min_mm": 60}
    assert outlook.township_outlook([], fc, now, cfg) is None


def test_warning_with_quiet_forecast_uses_the_warning_window(cfg):
    a = outlook.township_outlook(warnings("met_thunderstorm_klang_listed.json"), hourly(NOW, QUIET), NOW, cfg)
    assert (a.window_start, a.window_end) == (NOW, datetime(2026, 10, 16, 20, 0))


def test_both_reasons_when_both_fire_and_caveat_in_both_languages(cfg):
    a = outlook.township_outlook(warnings("met_thunderstorm_klang_listed.json"), hourly(NOW, {8: 50.0}), NOW, cfg)
    assert [r.code for r in a.reasons] == ["met_warning", "forecast_rain"]
    assert (a.window_start, a.window_end) == (NOW + timedelta(hours=8), NOW + timedelta(hours=9))
    for r in a.reasons:
        assert "miss" in r.text_en and "tropical storms" in r.text_en
        assert "ribut tropika" in r.text_ms


def test_expired_warning_is_ignored(cfg):
    now = datetime(2026, 10, 16, 21, 0)
    assert outlook.township_outlook(warnings("met_thunderstorm_klang_listed.json"), hourly(now, QUIET), now, cfg) is None


# ---------- cooldown and all-clear ----------

def test_cooldown_and_all_clear(cfg):
    cand = outlook.township_outlook(warnings("met_thunderstorm_klang_listed.json"), hourly(NOW, QUIET), NOW, cfg)
    first = outlook.issue_outlook(cand, None, NOW, cfg)
    assert first is cand
    for minutes in (30, 90):                                  # still active: no repeat
        t = NOW + timedelta(minutes=minutes)
        assert outlook.issue_outlook(replace(cand, issued_at=t), first, t, cfg) is None
    clear = outlook.issue_outlook(None, first, NOW + timedelta(minutes=45), cfg)
    assert clear.kind == "all_clear" and clear.level is Level.NORMAL and clear.street_id == "BBR" and clear.reasons == ()
    assert outlook.issue_outlook(None, clear, NOW + timedelta(minutes=60), cfg) is None
    # back within 60 min of the last outlook row: suppressed; after it: issued
    t = NOW + timedelta(minutes=75)                           # 30 min after the all-clear (at +45)
    assert outlook.issue_outlook(replace(cand, issued_at=t), clear, t, cfg) is None
    t = NOW + timedelta(minutes=105)
    again = replace(cand, issued_at=t)
    assert outlook.issue_outlook(again, clear, t, cfg) is again


def test_quiet_when_nothing_to_say(cfg):
    assert outlook.issue_outlook(None, None, NOW, cfg) is None


def test_loaders_read_the_latest_saved_files(tmp_path):
    import gzip
    day = tmp_path / "met" / "json" / "2026-10-16"
    day.mkdir(parents=True)
    raw = (FIX / "met_thunderstorm_klang_listed.json").read_bytes()
    (day / "1500.json.gz").write_bytes(gzip.compress(b"[]"))
    (day / "1600.json.gz").write_bytes(gzip.compress(raw))
    assert len(met_parse.load_latest(tmp_path / "met")) == 1
    assert met_parse.load_latest(tmp_path / "none") == []
    t = pd.Timestamp("2026-10-16 18:00")
    rows = [{"point_id": p, "model": "best_match", "time_local": t, "precip_mm": mm, "fetched_at_local": f}
            for p, mm, f in [("BBR", 1.0, pd.Timestamp("2026-10-16 10:00")), ("BBR", 9.0, pd.Timestamp("2026-10-16 11:00")),
                             ("USJ", 5.0, pd.Timestamp("2026-10-16 11:00"))]]
    (tmp_path / "om").mkdir()
    pd.DataFrame(rows).to_parquet(tmp_path / "om" / "2026-10-16.parquet")
    assert outlook.load_forecast(tmp_path / "om", "BBR").precip_mm.tolist() == [9.0]
    assert outlook.load_forecast(tmp_path / "nope", "BBR").empty
