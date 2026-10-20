"""Street states: level from the risk matrix, time window and reasons (build plan task E4)."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from .matrix import street_level
from .types import Level, MLResult, StreetState, TriggerResult


def combine(rule: TriggerResult, ml: MLResult | None, ml_cfg: dict) -> TriggerResult:
    """Two-tier trigger: the rules decide Warning and Danger. ML may raise the trigger only while
    `ml_drives_alerts` is true (set by the evaluation gate), and then only up to `ml_max_level`
    (default watch, and never above watch whatever the config says). ML never lowers a rule level. The ML probability is always shown as a reason."""
    if ml is None:
        return rule
    drives = bool(ml_cfg.get("ml_drives_alerts", False))
    # Hard cap in code: config may only lower it. Warning and Danger come only from the rules.
    ml_level = min(ml.level, Level.WATCH, Level.parse(ml_cfg.get("ml_max_level", "watch")))
    level = max(rule.level, ml_level) if drives else rule.level
    fired = list(rule.fired_by) if rule.level == level else []
    if drives and ml_level == level and level > Level.NORMAL:
        fired.append("model")
    ml_first = drives and ml_level >= rule.level and ml_level > Level.NORMAL
    reasons = ml.reasons + rule.reasons if ml_first or rule.level == Level.NORMAL else rule.reasons + ml.reasons
    return TriggerResult(level=level, confidence=rule.confidence, fired_by=tuple(fired), reasons=reasons,
                         data_time=rule.data_time, stale_stations=rule.stale_stations)


def min_alert_level(rules_cfg: dict) -> Level:
    return min(Level.parse(name) for name in rules_cfg["alerts"]["alert_levels"])


def street_states(streets: pd.DataFrame, trigger: TriggerResult, rules_cfg: dict, matrix_table: dict,
                  flood_probability: float | None = None) -> list[StreetState]:
    """One state per street. Streets at an alert level get the nowcast window."""
    return [street_state(street_id, int(susceptibility), trigger, rules_cfg, matrix_table, flood_probability)
            for street_id, susceptibility in zip(streets["street_id"], streets["susceptibility"])]


def street_state(street_id: str, susceptibility: int, trigger: TriggerResult, rules_cfg: dict, matrix_table: dict,
                 flood_probability: float | None = None) -> StreetState:
    """One street's state from its own trigger. Streets at an alert level get the nowcast window."""
    window = rules_cfg["nowcast_window_min"]
    level = street_level(susceptibility, trigger.level, matrix_table)
    has_window = level >= Level.parse(rules_cfg["alerts"].get("window_from", "warning"))
    return StreetState(
        street_id=street_id, level=level, trigger_level=trigger.level, confidence=trigger.confidence,
        flood_probability=flood_probability, fired_by=trigger.fired_by,
        window_start=trigger.data_time + timedelta(minutes=window["start"]) if has_window else None,
        window_end=trigger.data_time + timedelta(minutes=window["end"]) if has_window else None,
        reasons=trigger.reasons if level > Level.NORMAL or trigger.confidence != "high" else (),
        data_time=trigger.data_time,
    )
