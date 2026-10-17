"""WP2: a street whose own river station is dead or stale falls back to its next candidate."""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from floodready.engine import replay
from floodready.engine import street_stations as ss
from floodready.engine.types import Level

from conftest import BBR_STATIONS

T = lambda hhmm: datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731

# ---- mapping helpers ----
MAP = {
    "S": {"wl": "26558", "wl_candidates": ["26558", "PEKANMERU", "PANDAMARAN"], "rf": [], "method": "flow", "distance_m": 1.0},
    "OLD": {"wl": "W1", "rf": [], "method": "flow", "distance_m": 1.0},        # file written before WP2
    "NONE": {"wl": None, "rf": ["R"], "method": None, "distance_m": None},
}


def test_candidates_flow_path_first_then_nearest_deduped():
    wl = [("W1", 3.10, 101.40), ("W2", 3.11, 101.40), ("W3", 3.12, 101.40), ("W4", 3.60, 101.40)]
    hits = [("W3", 9_000.0), ("W1", 12_000.0), ("W4", 14_000.0)]
    out = ss.pick_wl_candidates(hits, wl, 3.105, 101.40, {"river_radius_km": 10})
    # flow order W3, W1, W4 (within 15 km along the path), then other in-radius stations nearest first (W2)
    assert [c[0] for c in out] == ["W3", "W1", "W4", "W2"]
    assert out[0][1] == "flow" and out[-1][1] == "nearest"


def test_candidates_drop_far_flow_hits_and_stations_outside_the_radius():
    wl = [("W1", 3.10, 101.40), ("W2", 3.30, 101.40)]
    assert [c[0] for c in ss.pick_wl_candidates([("W2", 16_000.0)], wl, 3.102, 101.40, {"river_radius_km": 10})] == ["W1"]
    assert ss.pick_wl_candidates([], wl, 3.70, 101.40, {"river_radius_km": 5}) == []


def test_pick_wl_is_the_first_candidate():
    wl = [("W1", 3.10, 101.40), ("W2", 3.11, 101.40)]
    hits = [("W2", 9_000.0)]
    assert ss.pick_wl(hits, wl, 3.105, 101.40) == ss.pick_wl_candidates(hits, wl, 3.105, 101.40)[0]


def test_candidates_for_reads_old_files_and_streets_without_a_river_station():
    assert ss.candidates_for(MAP, "S") == ("26558", "PEKANMERU", "PANDAMARAN")
    assert ss.candidates_for(MAP, "OLD") == ("W1",)
    assert ss.candidates_for(MAP, "NONE") == () and ss.candidates_for(MAP, "missing") == () and ss.candidates_for(None, "S") == ()


def test_wl_for_skips_dead_stations_in_order():
    assert ss.wl_for(MAP, "S") == "26558"
    assert ss.wl_for(MAP, "S", set()) == "26558"
    assert ss.wl_for(MAP, "S", {"26558"}) == "PEKANMERU"
    assert ss.wl_for(MAP, "S", {"26558", "PEKANMERU"}) == "PANDAMARAN"
    assert ss.wl_for(MAP, "S", {"26558", "PEKANMERU", "PANDAMARAN"}) is None
    assert ss.wl_for(MAP, "NONE", {"x"}) is None and ss.wl_for(None, "S", {"x"}) is None


def test_dead_wl_is_a_missing_or_stale_river_row():
    feats = pd.DataFrame({"graph_id": ["A", "B", "R"], "kind": ["wl", "wl", "rf"], "is_stale": [False, True, False]})
    assert ss.dead_wl(feats, ["A", "B", "C"]) == {"B", "C"}      # B stale, C no row
    assert ss.dead_wl(feats, ["R"]) == {"R"}                     # a rain row is not a river reading
    assert ss.dead_wl(feats.iloc[0:0], ["A"]) == {"A"}


# ---- replay ----
STREETS = pd.DataFrame({"street_id": ["fb", "solo", "alone"], "susceptibility": [5, 5, 5]})


def mapping(rf=()):
    return {
        "fb": {"wl": "26558", "wl_candidates": ["26558", "PEKANMERU"], "rf": list(rf), "method": "flow", "distance_m": 1.0},
        "solo": {"wl": "26558", "wl_candidates": ["26558"], "rf": list(rf), "method": "flow", "distance_m": 1.0},
        "alone": {"wl": "PEKANMERU", "wl_candidates": ["PEKANMERU"], "rf": [], "method": "flow", "distance_m": 1.0},
    }


def blank_wl(readings, graph_id, since=None):
    out = readings.copy()
    hit = (out.graph_id == graph_id) & (out.kind == "wl")
    if since is not None:
        hit &= out.time_local >= pd.Timestamp(since)
    out.loc[hit, "wl_m"] = np.nan
    return out


def run(readings, stations, rules_cfg, matrix_cfg, mapping_, **kw):
    return {s.time: s for s in replay.run(T("06:00"), T("11:00"), timedelta(minutes=15), readings, stations, STREETS,
                                          BBR_STATIONS, rules_cfg, matrix_cfg, street_stations=mapping_, **kw)}


def state(step, street):
    return next(s for s in step.states if s.street_id == street)


def test_dead_first_station_falls_back_for_river_rules_and_names_the_station(readings, stations, rules_cfg, matrix_cfg):
    steps = run(blank_wl(readings, "26558"), stations, rules_cfg, matrix_cfg, mapping())
    peak = steps[T("10:00")]
    fb, alone = state(peak, "fb"), state(peak, "alone")
    assert alone.level >= Level.WARNING                              # PEKANMERU alone reaches at least Warning
    assert fb.level == alone.level and fb.trigger_level == alone.trigger_level
    river = [r for r in fb.reasons if r.code == "river_level"]
    assert river and all("Pekan Meru" in r.text_en for r in river)   # the station actually used
    assert not any(r.code == "stale_data" for r in fb.reasons)


def test_all_candidates_dead_keeps_rain_rules_and_adds_stale_data(readings, stations, rules_cfg, matrix_cfg):
    steps = run(blank_wl(readings, "26558"), stations, rules_cfg, matrix_cfg, mapping(("26558",)))   # its rain is at Warning at 09:30
    at = steps[T("09:30")]
    solo = state(at, "solo")
    assert any(r.code == "stale_data" for r in solo.reasons)
    assert any(r.code.startswith("rain") for r in solo.reasons)      # rain rules still fire
    assert solo.level >= Level.WATCH                                 # never silently lowered
    assert solo.confidence == "medium"                               # rain reports, the river is blind
    early = state(steps[T("06:00")], "solo")                         # quiet rain, dead river: still told why
    assert early.level is Level.NORMAL and early.reasons[0].code == "stale_data"
    stale = next(r for r in solo.reasons if r.code == "stale_data")
    assert "river" in stale.text_en.lower() and "sungai" in stale.text_ms.lower()


def test_healthy_first_station_is_kept(readings, stations, rules_cfg, matrix_cfg):
    healthy = {"x": {"wl": "PEKANMERU", "wl_candidates": ["PEKANMERU", "PANDAMARAN"], "rf": [], "method": "flow",
                     "distance_m": 1.0}}
    streets = pd.DataFrame({"street_id": ["x"], "susceptibility": [5]})
    only = {"x": {"wl": "PEKANMERU", "wl_candidates": ["PEKANMERU"], "rf": [], "method": "flow", "distance_m": 1.0}}
    a = list(replay.run(T("09:00"), T("10:00"), timedelta(minutes=15), readings, stations, streets, BBR_STATIONS,
                        rules_cfg, matrix_cfg, street_stations=healthy))
    b = list(replay.run(T("09:00"), T("10:00"), timedelta(minutes=15), readings, stations, streets, BBR_STATIONS,
                        rules_cfg, matrix_cfg, street_stations=only))
    assert [s.states[0].level for s in a] == [s.states[0].level for s in b]


def test_station_that_dies_after_t_is_still_used_at_t(readings, stations, rules_cfg, matrix_cfg):
    """No look-ahead: PEKANMERU stops reporting at 09:30; at 09:00 the first candidate is still its own station."""
    both = {"x": {"wl": "PEKANMERU", "wl_candidates": ["PEKANMERU", "PANDAMARAN"], "rf": [], "method": "flow",
                  "distance_m": 1.0}}
    streets = pd.DataFrame({"street_id": ["x"], "susceptibility": [5]})
    full = list(replay.run(T("08:00"), T("11:00"), timedelta(minutes=15), readings, stations, streets, BBR_STATIONS,
                           rules_cfg, matrix_cfg, street_stations=both))
    cut = list(replay.run(T("08:00"), T("11:00"), timedelta(minutes=15), blank_wl(readings, "PEKANMERU", "2024-11-12 09:30"),
                          stations, streets, BBR_STATIONS, rules_cfg, matrix_cfg, street_stations=both))
    by_full, by_cut = {s.time: s.states[0] for s in full}, {s.time: s.states[0] for s in cut}
    for hhmm in ("08:00", "08:30", "09:00", "09:15"):
        assert by_cut[T(hhmm)].level == by_full[T(hhmm)].level
        assert [r.text_en for r in by_cut[T(hhmm)].reasons] == [r.text_en for r in by_full[T(hhmm)].reasons]
    # 09:30 itself: PEKANMERU is blank but its last level is carried for 2 h (stale only after stale_after_min)
    assert not any(r.code == "stale_data" for r in by_cut[T("09:30")].reasons)


class HalfModel:
    def predict_proba(self, X):
        return np.column_stack([np.full(len(X), 0.5), np.full(len(X), 0.5)])


def test_ml_probability_comes_from_the_fallback_station(readings, stations, rules_cfg, matrix_cfg):
    from floodready.ml import dataset
    ml_cfg = {"p_watch": 0.35, "p_warning": 0.4, "smoothing_min": 30, "horizon_h": 2, "ml_drives_alerts": False,
              "ml_max_level": "watch"}
    bundle = {"model": HalfModel(), "features": dataset.FEATURES}
    steps = run(blank_wl(readings, "26558"), stations, rules_cfg, matrix_cfg, mapping(), ml_bundle=bundle, ml_cfg=ml_cfg,
                wl_ids=["26558", "PEKANMERU", "PANDAMARAN"])
    at = steps[T("09:00")]
    assert state(at, "fb").flood_probability == 0.5          # via PEKANMERU
    assert state(at, "solo").flood_probability is None       # every candidate dead: no ML either
