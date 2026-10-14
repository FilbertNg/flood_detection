from datetime import datetime

import numpy as np
import pandas as pd

from floodready.engine import features, rules
from floodready.engine.types import Level

from conftest import BBR_STATIONS

T = lambda hhmm: datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731


def trigger_at(readings, stations, rules_cfg, hhmm):
    feats = features.station_features(readings, T(hhmm), stations)
    return rules.township_trigger(feats, BBR_STATIONS, rules_cfg)


def test_quiet_morning_is_normal(readings, stations, rules_cfg):
    result = trigger_at(readings, stations, rules_cfg, "08:30")
    assert result.level is Level.NORMAL and result.confidence == "high"


def test_watch_at_0845_from_heavy_rain_at_kg_perepat(readings, stations, rules_cfg):
    result = trigger_at(readings, stations, rules_cfg, "08:45")
    assert result.level is Level.WATCH
    top = result.reasons[0]
    assert (top.code, top.value, top.station) == ("rain_1h", 45.0, "Kg. Perepat, Kapar")


def test_warning_at_0900_from_very_heavy_rain(readings, stations, rules_cfg):
    result = trigger_at(readings, stations, rules_cfg, "09:00")
    assert result.level is Level.WARNING
    assert result.fired_by == ("rule_rain",)
    assert result.reasons[0].text_en == "61.5 mm of rain in 1 h at Kg. Perepat, Kapar"
    assert result.reasons[0].text_ms == "Hujan 61.5 mm dalam 1 jam di Kg. Perepat, Kapar"


def test_warning_at_0930_from_rain_and_river(readings, stations, rules_cfg):
    result = trigger_at(readings, stations, rules_cfg, "09:30")
    assert result.level is Level.WARNING
    assert set(result.fired_by) == {"rule_rain", "rule_river"}


def test_danger_at_1000_when_sg_binjai_passes_its_danger_level(readings, stations, rules_cfg):
    result = trigger_at(readings, stations, rules_cfg, "10:00")
    assert result.level is Level.DANGER
    assert result.fired_by == ("rule_river",)
    top = result.reasons[0]
    assert (top.code, top.value, top.station) == ("river_level", 4.21, "Sg. Binjai di Pekan Meru")
    assert "danger level" in top.text_en and "bahaya" in top.text_ms


def test_all_stations_stale_is_flagged_not_silently_normal(stations, rules_cfg):
    old = pd.DataFrame([{"graph_id": "26558", "kind": "rf", "time_local": T("03:00"), "rain_15min_mm": 0.0, "wl_m": np.nan}])
    feats = features.station_features(old, T("09:00"), stations)
    result = rules.township_trigger(feats, BBR_STATIONS, rules_cfg)
    assert result.confidence == "low"
    assert result.reasons[0].code == "stale_data"
    assert set(result.stale_stations) == set(BBR_STATIONS)
