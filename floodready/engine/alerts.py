"""Alert issuing with cooldown and all-clear (build plan task E5).

- An alert when a street enters an alert level (warning or danger).
- No repeat within the cooldown unless the level rises above the last alert.
- One all-clear when a street that had an alert returns to normal, but not before the alert is at least
  `alerts.clear_after_min` old (default: the cooldown). Rain that hovers around a threshold rolls on and off every
  15-30 min; without the hold that gave alert, all-clear, alert, all-clear. While held the alert stays active and the
  next tick re-checks. Holding an all-clear never lowers a warning, and a rising level still alerts at once.
  The hold only delays the notification. The API keeps the alert active (`repo.list_alerts`, `serialize.street_detail`)
  while the street is elevated or its state is less than `clear_after_min` past the alert, so residents still see it,
  can confirm it, and are not re-notified if the level comes back inside the hold.
- Known limitation: the hold counts from the alert's issue time, not from when the street went quiet. An alert older
  than the hold is cleared on the first Normal tick, and a same-level re-entry alerts again after the cooldown. Holding
  until the street has been continuously Normal needs per-street "normal since" state (an interface change).
"""
from __future__ import annotations

from datetime import timedelta

from .levels import min_alert_level
from .types import Alert, Level, StreetState

# The live runner recomputes the last 3 h on every refresh, so the hold is rebuilt from readings after a restart
# only while it is shorter than that window.
LIVE_WINDOW_MIN = 180


def clear_after(alerts_cfg: dict) -> timedelta:
    """`alerts.clear_after_min` (default: the cooldown), the minimum alert age before an all-clear."""
    minutes = alerts_cfg.get("clear_after_min")
    if minutes is None:
        minutes = alerts_cfg["cooldown_min"]
    if minutes >= LIVE_WINDOW_MIN:
        raise ValueError(f"alerts.clear_after_min ({minutes}) must be below the {LIVE_WINDOW_MIN} min live recompute window")
    return timedelta(minutes=minutes)


def issue(prev: dict[str, StreetState], new: list[StreetState], last_alerts: dict[str, Alert],
          cfg: dict) -> list[Alert]:
    """`prev`: last state per street; `last_alerts`: last alert or all-clear per street."""
    alert_from = min_alert_level(cfg)
    cooldown = timedelta(minutes=cfg["alerts"]["cooldown_min"])
    clear_after_ = clear_after(cfg["alerts"])
    issued = []
    for state in new:
        before = prev.get(state.street_id)
        prev_level = before.level if before else Level.NORMAL
        last = last_alerts.get(state.street_id)
        active = last is not None and last.kind == "alert"

        if state.level >= alert_from:
            rising = active and state.level > last.level
            entering = prev_level < state.level and (not active or state.data_time - last.issued_at >= cooldown)
            if not active or rising or entering:
                issued.append(_make(state, "alert"))
        elif state.level == Level.NORMAL and active and state.data_time - last.issued_at >= clear_after_:
            issued.append(_make(state, "all_clear"))
    return issued


def _make(state: StreetState, kind: str) -> Alert:
    return Alert(street_id=state.street_id, level=state.level, kind=kind, issued_at=state.data_time,
                 window_start=state.window_start if kind == "alert" else None,
                 window_end=state.window_end if kind == "alert" else None,
                 reasons=state.reasons if kind == "alert" else (), fired_by=state.fired_by if kind == "alert" else ())
