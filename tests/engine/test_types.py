import re
from dataclasses import FrozenInstanceError
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from floodready.engine.types import Alert, Level, MLResult, Reason, StreetState, TriggerResult

ROOT = Path(__file__).resolve().parents[2]
LEVEL_NAMES = ["normal", "watch", "warning", "danger"]


def load_config(name):
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


# ---------- Level ----------

def test_levels_order():
    assert Level.DANGER > Level.WARNING > Level.WATCH > Level.NORMAL
    assert max(Level.WATCH, Level.WARNING) is Level.WARNING


def test_level_names_round_trip_as_lowercase_json():
    assert [lv.json for lv in Level] == LEVEL_NAMES
    assert [Level.parse(name) for name in LEVEL_NAMES] == list(Level)
    with pytest.raises(ValueError):
        Level.parse("severe")


def test_typescript_level_union_matches_python():
    ts = (ROOT / "packages" / "shared" / "src" / "api" / "types.ts").read_text(encoding="utf-8")
    union = re.search(r"export type Level\s*=\s*([^;]+);", ts).group(1)
    assert re.findall(r"'([a-z_]+)'", union) == LEVEL_NAMES


# ---------- dataclasses ----------

def reason():
    return Reason(code="rain_1h", value=61.5, unit="mm", station="Kg. Perepat, Kapar",
                  text_en="61.5 mm of rain in 1 h at Kg. Perepat, Kapar",
                  text_ms="Hujan 61.5 mm dalam 1 jam di Kg. Perepat, Kapar")


def test_engine_records_are_immutable_and_hold_contract_fields():
    at = datetime(2024, 11, 12, 9, 0)
    trigger = TriggerResult(level=Level.WARNING, confidence="high", fired_by=("rule_rain",),
                            reasons=(reason(),), data_time=at, stale_stations=())
    ml = MLResult(p=0.62, level=Level.WATCH, station="Sg. Binjai di Pekan Meru", horizon_h=2, reasons=())
    state = StreetState(street_id="BBR-jalan-makyong", level=Level.WARNING, trigger_level=trigger.level,
                        confidence="high", flood_probability=ml.p, fired_by=trigger.fired_by,
                        window_start=datetime(2024, 11, 12, 9, 30), window_end=datetime(2024, 11, 12, 10, 30),
                        reasons=trigger.reasons, data_time=at)
    alert = Alert(street_id=state.street_id, level=state.level, kind="alert", issued_at=at,
                  window_start=state.window_start, window_end=state.window_end,
                  reasons=state.reasons, fired_by=state.fired_by)
    assert alert.reasons[0].text_ms.startswith("Hujan 61.5 mm")
    with pytest.raises(FrozenInstanceError):
        state.level = Level.DANGER


# ---------- config files (build plan §2) ----------

def test_risk_matrix_config_complete():
    matrix = load_config("risk_matrix.yaml")["matrix"]
    assert sorted(matrix) == [1, 2, 3, 4, 5]
    for row in matrix.values():
        assert list(row) == LEVEL_NAMES
        assert all(value in LEVEL_NAMES for value in row.values())


def test_risk_matrix_matches_plan_examples():
    matrix = load_config("risk_matrix.yaml")["matrix"]
    assert matrix[5]["warning"] == "warning"
    assert matrix[2]["warning"] == "watch"
    assert matrix[1]["watch"] == "normal"
    assert matrix[4]["danger"] == "danger"
    # Never above the trigger level, and never lower for a more susceptible street.
    for trigger in LEVEL_NAMES:
        column = [LEVEL_NAMES.index(matrix[s][trigger]) for s in range(1, 6)]
        assert column == sorted(column)
        assert max(column) <= LEVEL_NAMES.index(trigger)


def test_rules_config_uses_jps_figures():
    rules = load_config("rules.yaml")
    assert rules["rain"]["watch"] == {"rain_1h_min_mm": 31, "rain_2to4h_min_mm": 40}
    assert rules["rain"]["warning"] == {"rain_1h_above_mm": 60, "rain_2to4h_min_mm": 60}
    assert rules["river"] == {"alert": "watch", "warning": "warning", "danger": "danger"}
    assert rules["alerts"]["cooldown_min"] == 60
    assert rules["nowcast_window_min"] == {"start": 30, "end": 90}


def test_ml_config_is_set_by_gate_v2():
    ml = load_config("ml.yaml")
    assert 0 < ml["p_watch"] < ml["p_warning"] < 1
    assert isinstance(ml["ml_drives_alerts"], bool)  # only the gate (train_trigger.py) may set this
    assert ml["ml_max_level"] == "watch" and ml["gate_version"] == 2
    assert ml["gate"] == {"min_extra_lead_min": 30, "max_false_alarm_ratio": 1.5, "min_fresh_crossings": 30}


def test_ml_config_agrees_with_the_trained_model_card():
    import json
    from pathlib import Path
    ml = load_config("ml.yaml")
    card = json.loads((Path(__file__).resolve().parents[2] / "models" / "trigger_v1.json").read_text(encoding="utf-8"))
    assert ml["ml_drives_alerts"] == card["gate_passed"]   # a hand edit of the yaml cannot switch ML on
    assert ml["p_watch"] == card["p_watch"] and ml["gate_version"] == card["gate_version"] == 2


def test_with_the_real_config_ml_alone_never_goes_above_watch():
    """Needs the ml_max_level cap in levels.combine (WP5, #17). Fails on a main without it, so #22 cannot land first."""
    from datetime import datetime
    from floodready.engine.levels import combine
    from floodready.engine.types import Level, TriggerResult
    from floodready.ml.predict import ml_result
    cfg = load_config("ml.yaml")
    rule = TriggerResult(level=Level.NORMAL, confidence="high", fired_by=(), reasons=(),
                         data_time=datetime(2024, 11, 12, 9, 0), stale_stations=())
    assert combine(rule, ml_result(0.99, "X", cfg), cfg).level <= Level.WATCH
