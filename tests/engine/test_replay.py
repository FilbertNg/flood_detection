from datetime import datetime, timedelta

import pandas as pd

from floodready.engine import replay
from floodready.engine.types import Level

from conftest import BBR_STATIONS

T = lambda hhmm: datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731
STREETS = pd.DataFrame({"street_id": ["BBR-prone", "BBR-safe"], "susceptibility": [5, 1]})


def run(readings, stations, rules_cfg, matrix_cfg):
    return list(replay.run(T("06:00"), T("14:00"), timedelta(minutes=15), readings, stations, STREETS,
                           BBR_STATIONS, rules_cfg, matrix_cfg))


def test_replay_reproduces_the_12_nov_2024_trigger_timeline(readings, stations, rules_cfg, matrix_cfg):
    steps = run(readings, stations, rules_cfg, matrix_cfg)
    assert steps[0].time == T("06:00") and steps[-1].time == T("14:00") and len(steps) == 33
    changes, last = [], None
    for step in steps:
        if step.trigger.level != last:
            changes.append((step.time, step.trigger.level))
            last = step.trigger.level
    assert changes[:4] == [(T("06:00"), Level.NORMAL), (T("08:45"), Level.WATCH),
                           (T("09:00"), Level.WARNING), (T("10:00"), Level.DANGER)]


def test_replay_alerts_the_flood_prone_street_only(readings, stations, rules_cfg, matrix_cfg):
    steps = run(readings, stations, rules_cfg, matrix_cfg)
    issued = [(a.street_id, a.kind, a.level, a.issued_at) for step in steps for a in step.alerts]
    assert issued[:2] == [("BBR-prone", "alert", Level.WARNING, T("09:00")),
                          ("BBR-prone", "alert", Level.DANGER, T("10:00"))]
    assert all(street == "BBR-prone" for street, *_ in issued)


def test_replay_states_cover_every_street_at_every_step(readings, stations, rules_cfg, matrix_cfg):
    steps = run(readings, stations, rules_cfg, matrix_cfg)
    assert all({s.street_id for s in step.states} == {"BBR-prone", "BBR-safe"} for step in steps)
    at_nine = next(step for step in steps if step.time == T("09:00"))
    prone = next(s for s in at_nine.states if s.street_id == "BBR-prone")
    assert (prone.window_start, prone.window_end) == (T("09:30"), T("10:30"))
