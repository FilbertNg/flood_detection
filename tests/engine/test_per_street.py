"""Per-street triggers and the two-tier ML cap (WP5)."""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from floodready.engine import alerts, levels, replay
from floodready.engine.types import Level, MLResult, Reason, StreetState, TriggerResult
from floodready.ml import predict

from conftest import BBR_STATIONS

T = lambda hhmm: datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731
STREETS = pd.DataFrame({"street_id": ["near-perepat", "near-rantau", "no-wl", "unmapped"], "susceptibility": [5, 5, 5, 5]})
MAPPING = {
    "near-perepat": {"wl": "PEKANMERU", "rf": ["26558"], "method": "flow", "distance_m": 1.0},
    "near-rantau": {"wl": None, "rf": ["KGRANTAUPANJANG"], "method": None, "distance_m": None},
    "no-wl": {"wl": None, "rf": ["26558", "TELOKGONG"], "method": None, "distance_m": None},
}
RAIN = Reason("rain_1h", 61.5, "mm", "X", "61.5 mm of rain in 1 h at X", "Hujan")


def run(readings, stations, rules_cfg, matrix_cfg, mapping=MAPPING, **kw):
    return list(replay.run(T("06:00"), T("11:00"), timedelta(minutes=15), readings, stations, STREETS, BBR_STATIONS,
                           rules_cfg, matrix_cfg, street_stations=mapping, **kw))


def level_of(step, street):
    return next(s.level for s in step.states if s.street_id == street)


def test_each_street_uses_only_its_own_stations(readings, stations, rules_cfg, matrix_cfg):
    steps = {s.time: s for s in run(readings, stations, rules_cfg, matrix_cfg)}
    at = steps[T("09:30")]
    # 26558 rain is at Warning at 09:30; Kg. Rantau Panjang is quiet
    assert level_of(at, "near-perepat") is Level.WARNING
    assert level_of(at, "near-rantau") is Level.NORMAL
    assert level_of(at, "no-wl") is Level.WARNING          # rain gauges only, no river station
    assert level_of(at, "unmapped") is Level.WARNING       # not in the mapping: township-wide trigger
    quiet = next(s for s in at.states if s.street_id == "near-rantau")
    assert quiet.trigger_level is Level.NORMAL and quiet.reasons == ()


def test_without_a_mapping_every_street_gets_the_township_trigger(readings, stations, rules_cfg, matrix_cfg):
    steps = run(readings, stations, rules_cfg, matrix_cfg, mapping=None)
    at = next(s for s in steps if s.time == T("09:30"))
    assert {s.level for s in at.states} == {Level.WARNING}


def test_a_street_whose_stations_are_all_stale_has_low_confidence(readings, stations, rules_cfg, matrix_cfg):
    gone = readings[readings.graph_id != "KGRANTAUPANJANG"]
    at = next(s for s in run(gone, stations, rules_cfg, matrix_cfg) if s.time == T("09:30"))
    rantau = next(s for s in at.states if s.street_id == "near-rantau")
    perepat = next(s for s in at.states if s.street_id == "near-perepat")
    assert rantau.confidence == "low" and perepat.confidence == "high"


class FixedModel:
    """Probability = the feature value d_warning, so each station can be given its own probability."""
    def predict_proba(self, X):
        p = X["d_warning"].to_numpy()
        return np.column_stack([1 - p, p])


def test_station_probabilities_one_result_per_river_station():
    cols = {"d_warning": 0.0}
    t = pd.Timestamp(T("09:00"))
    feats = pd.DataFrame([
        {"graph_id": "A", "name": "Sg A", "time_local": t, **{**cols, "d_warning": 0.2}},
        {"graph_id": "A", "name": "Sg A", "time_local": t - timedelta(minutes=15), **{**cols, "d_warning": 0.6}},
        {"graph_id": "B", "name": "Sg B", "time_local": t, **{**cols, "d_warning": 0.1}},
    ])
    cfg = {"p_watch": 0.35, "p_warning": 0.95, "smoothing_min": 30, "horizon_h": 2}
    res = predict.station_probabilities(FixedModel(), ["d_warning"], feats, ["A", "B", "C"], T("09:00"), cfg)
    assert set(res) == {"A", "B"}                           # C has no rows
    assert res["A"].p == 0.6 and res["A"].level is Level.WATCH and res["A"].station == "Sg A"
    assert res["B"].level is Level.NORMAL
    total = predict.township_probability(FixedModel(), ["d_warning"], feats, ["A", "B"], T("09:00"), cfg)
    assert total.p == 0.6


# ---- two-tier combine ----
def rule(level):
    return TriggerResult(level=level, confidence="high", fired_by=("rule_rain",) if level else (),
                         reasons=(RAIN,) if level else (), data_time=T("09:00"), stale_stations=())


def ml(level, p=0.99):
    r = Reason("ml_probability", p, "p", "Sg", f"{round(p*100)}% chance", "kemungkinan")
    return MLResult(p=p, level=level, station="Sg", horizon_h=2, reasons=(r,))


DRIVES = {"ml_drives_alerts": True, "ml_max_level": "watch"}


def test_ml_may_raise_normal_to_watch_and_goes_first():
    out = levels.combine(rule(Level.NORMAL), ml(Level.WATCH, 0.5), DRIVES)
    assert out.level is Level.WATCH and "model" in out.fired_by
    assert out.reasons[0].code == "ml_probability"


def test_ml_warning_is_capped_at_watch():
    out = levels.combine(rule(Level.NORMAL), ml(Level.WARNING), DRIVES)
    assert out.level is Level.WATCH


def test_default_cap_is_watch_when_unset():
    assert levels.combine(rule(Level.NORMAL), ml(Level.WARNING), {"ml_drives_alerts": True}).level is Level.WATCH


def test_ml_never_lowers_a_rule_warning_or_danger():
    for lv in (Level.WARNING, Level.DANGER):
        out = levels.combine(rule(lv), ml(Level.NORMAL, 0.01), DRIVES)
        assert out.level is lv and out.fired_by == ("rule_rain",)
        assert out.reasons[0].code == "rain_1h"


def test_rule_warning_is_not_changed_by_a_capped_ml():
    out = levels.combine(rule(Level.WARNING), ml(Level.WARNING), DRIVES)
    assert out.level is Level.WARNING and "model" not in out.fired_by
    assert out.reasons[0].code == "rain_1h"


def test_gate_closed_means_rules_only():
    out = levels.combine(rule(Level.NORMAL), ml(Level.WATCH), {"ml_drives_alerts": False, "ml_max_level": "watch"})
    assert out.level is Level.NORMAL


def test_config_cannot_let_ml_set_warning_or_danger():
    for cap in ("warning", "danger"):
        out = levels.combine(rule(Level.NORMAL), ml(Level.DANGER), {"ml_drives_alerts": True, "ml_max_level": cap})
        assert out.level is Level.WATCH


def test_config_can_lower_the_ml_cap_to_normal():
    out = levels.combine(rule(Level.NORMAL), ml(Level.WATCH), {"ml_drives_alerts": True, "ml_max_level": "normal"})
    assert out.level is Level.NORMAL


def trigger_of(level):
    return TriggerResult(level=level, confidence="high", fired_by=("rule_rain",), reasons=(RAIN,),
                         data_time=T("09:00"), stale_stations=())


def test_watch_streets_get_no_window_by_default_but_warning_does(rules_cfg, matrix_cfg):
    assert rules_cfg["alerts"]["window_from"] == "warning"
    watch = levels.street_state("s", 5, trigger_of(Level.WATCH), rules_cfg, matrix_cfg)
    warn = levels.street_state("s", 5, trigger_of(Level.WARNING), rules_cfg, matrix_cfg)
    assert watch.level is Level.WATCH and watch.window_start is None
    assert warn.window_start is not None


def test_group_cache_ignores_gauge_order(readings, stations, rules_cfg, matrix_cfg):
    from floodready.engine import rules
    calls = []
    real = rules.township_trigger
    rules.township_trigger = lambda *a, **k: (calls.append(1), real(*a, **k))[1]
    try:
        streets = pd.DataFrame({"street_id": ["a", "b"], "susceptibility": [5, 5]})
        m = {"a": {"wl": None, "rf": ["26558", "TELOKGONG"]}, "b": {"wl": None, "rf": ["TELOKGONG", "26558"]}}
        list(replay.run(T("09:00"), T("09:00"), timedelta(minutes=15), readings, stations, streets, BBR_STATIONS,
                        rules_cfg, matrix_cfg, street_stations=m))
    finally:
        rules.township_trigger = real
    assert len(calls) == 2      # township + one shared group


def test_unmapped_streets_are_logged_once(readings, stations, rules_cfg, matrix_cfg, caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        run(readings, stations, rules_cfg, matrix_cfg)
    assert sum("not in the street-stations mapping" in r.message for r in caplog.records) == 1


def test_station_probabilities_survive_a_duplicate_index():
    t = pd.Timestamp(T("09:00"))
    feats = pd.DataFrame({"graph_id": ["A", "A"], "name": ["Sg A"] * 2, "time_local": [t, t - timedelta(minutes=15)],
                          "d_warning": [0.2, 0.6]}, index=[0, 0])
    cfg = {"p_watch": 0.35, "p_warning": 0.95, "smoothing_min": 30, "horizon_h": 2}
    assert predict.station_probabilities(FixedModel(), ["d_warning"], feats, ["A"], T("09:00"), cfg)["A"].p == 0.6


def test_no_station_message_is_not_zero_of_zero():
    from floodready.engine import rules
    out = rules.township_trigger(pd.DataFrame(columns=["graph_id", "time_local", "is_stale", "kind"]), [], {"rain": {}, "river": {}})
    assert "0 of 0" not in out.reasons[0].text_en and out.confidence == "low"


# ---- watch notices ----
def state(level, when, street="s"):
    return StreetState(street_id=street, level=level, trigger_level=level, confidence="high", flood_probability=None,
                       fired_by=(), window_start=None, window_end=None, reasons=(), data_time=when)


def test_watch_notice_issued_when_watch_is_an_alert_level_and_a_rise_re_alerts():
    cfg = {"alerts": {"cooldown_min": 60, "alert_levels": ["watch", "warning", "danger"]}}
    first = alerts.issue({}, [state(Level.WATCH, T("09:00"))], {}, cfg)
    assert [(a.kind, a.level) for a in first] == [("alert", Level.WATCH)]
    last = {"s": first[0]}
    same = alerts.issue({"s": state(Level.WATCH, T("09:00"))}, [state(Level.WATCH, T("09:15"))], last, cfg)
    assert same == []                                                   # cooldown
    rise = alerts.issue({"s": state(Level.WATCH, T("09:15"))}, [state(Level.WARNING, T("09:30"))], last, cfg)
    assert [(a.kind, a.level) for a in rise] == [("alert", Level.WARNING)]   # rising level re-alerts inside the cooldown
    clear = alerts.issue({"s": state(Level.WATCH, T("09:15"))}, [state(Level.NORMAL, T("09:30"))], last, cfg)
    assert [a.kind for a in clear] == ["all_clear"]


def test_watch_is_not_alerted_when_not_listed():
    cfg = {"alerts": {"cooldown_min": 60, "alert_levels": ["warning", "danger"]}}
    assert alerts.issue({}, [state(Level.WATCH, T("09:00"))], {}, cfg) == []


def test_shipped_config_alerts_from_watch():
    import yaml
    from conftest import ROOT
    cfg = yaml.safe_load((ROOT / "config" / "rules.yaml").read_text(encoding="utf-8"))
    assert cfg["alerts"]["alert_levels"] == ["watch", "warning", "danger"]


class HalfModel:
    def predict_proba(self, X):
        return np.column_stack([np.full(len(X), 0.5), np.full(len(X), 0.5)])


def test_ml_applies_through_the_streets_own_river_station_and_is_capped_at_watch(readings, stations, rules_cfg, matrix_cfg):
    from floodready.ml import dataset
    ml_cfg = {"p_watch": 0.35, "p_warning": 0.4, "smoothing_min": 30, "horizon_h": 2, "ml_drives_alerts": True,
              "ml_max_level": "watch"}
    bundle = {"model": HalfModel(), "features": dataset.FEATURES}
    steps = run(readings, stations, rules_cfg, matrix_cfg, ml_bundle=bundle, ml_cfg=ml_cfg, wl_ids=["PEKANMERU", "PANDAMARAN"])
    at = next(s for s in steps if s.time == T("07:00"))        # rules are quiet at 07:00
    by_id = {s.street_id: s for s in at.states}
    assert by_id["near-perepat"].level is Level.WATCH and by_id["near-perepat"].flood_probability == 0.5
    assert by_id["near-perepat"].fired_by == ("model",)
    assert by_id["near-rantau"].level is Level.NORMAL and by_id["near-rantau"].flood_probability is None   # no river station
    peak = next(s for s in steps if s.time == T("09:30"))
    assert {s.street_id: s.level for s in peak.states}["near-perepat"] is Level.WARNING     # rules, not capped ML
