"""Statistics over a seeded database, checked against hand-computed numbers (WP8)."""
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from floodready.db import repo
from floodready.engine.types import Alert, Level, Reason
from floodready.stats import episodes as episodes_mod
from floodready.stats import statistics

FROM, TO = date(2024, 11, 1), date(2024, 11, 30)
NAMES = {"A": "Street A", "B": "Street B", "C": "Street C", "D": "Street D"}
STREET_STATIONS = {"A": {"rf": ["R1"]}, "C": {"rf": ["R1", "R2"]}}


def alert(street, level, at, kind="alert"):
    return Alert(street, level, kind, at, at + timedelta(minutes=30), at + timedelta(minutes=90),
                 (Reason("rain_1h", 60.0, "mm", "1", "Heavy rain", "Hujan lebat"),), ("rule_rain",))


def add_alert(conn, street, level, at, *, kind="alert", replay=False, backfill=True):
    return repo.insert_alerts(conn, [alert(street, level, at, kind)], is_replay=replay, is_backfill=backfill)[0]


def ans(conn, device, alert_id, street, kind="yes", at=None, **kw):
    repo.insert_answer(conn, {"device_id": device, "alert_id": alert_id, "street_id": street, "answer": kind,
                              "answered_at": at, **kw})


@pytest.fixture
def conn():
    with repo.connect("sqlite://").begin() as c:
        yield c


def slots(first: datetime, last: datetime):
    return pd.date_range(first, last, freq="15min")


@pytest.fixture
def readings():
    rows = []
    for t in slots(datetime(2024, 11, 12, 7, 0), datetime(2024, 11, 12, 9, 30)):
        rows.append(("R1", "rf", t, 1.0, np.nan))                  # 11 slots of 1 mm
    for t in slots(datetime(2024, 11, 20, 6, 0), datetime(2024, 11, 20, 9, 30)):
        rows.append(("R2", "rf", t, 2.0, np.nan))                  # 15 slots of 2 mm
        rows.append(("R1", "rf", t, 0.0, np.nan))
    return pd.DataFrame(rows, columns=["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"])


@pytest.fixture
def events():
    return pd.DataFrame([{
        "event_id": "BBR-2024-11-20-01", "street_id": "C", "start_time_local": "2024-11-20 09:30",
        "date_precision": "hour", "flooded": 1, "place_name": "Jalan C", "source_type": "news", "checked_by": "T", "status": "checked",
        "source_url": "https://example.org/c"}])


def seed(conn):
    """Four counted alerts (a1..a4) plus an all-clear; a5 is outside the period."""
    ids = {}
    ids["a1"] = add_alert(conn, "A", Level.WARNING, datetime(2024, 11, 12, 9, 0))
    ids["a2"] = add_alert(conn, "A", Level.DANGER, datetime(2024, 11, 12, 9, 15))
    ids["a3"] = add_alert(conn, "B", Level.WATCH, datetime(2024, 11, 13, 10, 0))
    ids["a4"] = add_alert(conn, "C", Level.WARNING, datetime(2024, 11, 20, 8, 0))
    add_alert(conn, "A", Level.NORMAL, datetime(2024, 11, 12, 11, 0), kind="all_clear")
    ids["a5"] = add_alert(conn, "A", Level.WARNING, datetime(2024, 12, 1, 9, 0))
    ans(conn, "d1", ids["a1"], "A", at=datetime(2024, 11, 12, 9, 40))
    ans(conn, "d2", ids["a1"], "A", at=datetime(2024, 11, 12, 9, 50))
    for i in range(3):
        ans(conn, f"n{i}", ids["a3"], "B", "no", datetime(2024, 11, 13, 10, 20))
    # a missed flood: two devices report on street D with no alert
    ans(conn, "m1", None, "D", "report", datetime(2024, 11, 25, 14, 0))
    ans(conn, "m2", None, "D", "report", datetime(2024, 11, 25, 14, 30))
    return ids


def extras(conn, readings, events):
    return statistics.analyse(conn, FROM, TO, street_names=NAMES, events=events, readings=readings,
                              street_stations=STREET_STATIONS)[2]


def run(conn, readings, events, **kw):
    return statistics.stats(conn, FROM, TO, street_names=NAMES, events=events, readings=readings,
                            street_stations=STREET_STATIONS, **kw)


def test_kpis_match_hand_computed(conn, readings, events):
    seed(conn)
    s = run(conn, readings, events)
    assert s["period"] == {"from": "2024-11-01", "to": "2024-11-30"}
    k = s["kpis"]
    # a1+a2 (street A, no all-clear between them) are ONE episode; the raw rows are kept separately
    assert (k["alerts"], k["confirmed"], k["not_confirmed"], k["unverified"]) == (3, 2, 1, 0)
    assert set(k) == {"alerts", "confirmed", "not_confirmed", "unverified", "confirmation_rate", "missed_floods",
                      "median_lead_min"}                                  # the frozen contract shape
    x = extras(conn, readings, events)
    assert x["alert_rows"] == 4 and x["street_days_with_alert"] == 3
    assert x["by_level"] == {"watch": 1, "warning": 1, "danger": 1}      # A reached danger, B watch, C warning
    assert k["confirmation_rate"] == pytest.approx(2 / 3)
    assert k["missed_floods"] == 1
    assert k["median_lead_min"] == 65.0          # (40 + 90) / 2


def test_by_week_street_sources_and_rain(conn, readings, events):
    seed(conn)
    s = run(conn, readings, events)
    assert s["by_week"] == [{"week": "2024-W46", "alerts": 2, "confirmed": 1},
                            {"week": "2024-W47", "alerts": 1, "confirmed": 1}]
    assert s["by_street"] == [
        {"street_id": "A", "name": "Street A", "alerts": 1, "confirmed": 1, "floods": 1},
        {"street_id": "C", "name": "Street C", "alerts": 1, "confirmed": 1, "floods": 1},
        {"street_id": "B", "name": "Street B", "alerts": 1, "confirmed": 0, "floods": 0}]
    assert s["sources"] == {"outcomes_from_news": 1, "outcomes_from_residents": 2}
    assert s["rain_at_onset"] == [{"street_id": "A", "event_date": "2024-11-12", "rain_2to4h_mm": 11.0},
                                  {"street_id": "C", "event_date": "2024-11-20", "rain_2to4h_mm": 30.0}]


def test_replay_demo_and_simulated_rows_change_nothing(conn, readings, events, monkeypatch):
    ids = seed(conn)
    monkeypatch.setattr(repo, "sensor_devices", lambda: {"sim-1": {"B"}, "real-1": {"B"}})
    before = run(conn, readings, events)
    # a replay alert with confirming demo answers, on a street that has counted alerts
    r = add_alert(conn, "A", Level.DANGER, datetime(2024, 11, 12, 9, 30), replay=True, backfill=False)
    ans(conn, "x1", r, "A", at=datetime(2024, 11, 12, 9, 40), source="demo")
    ans(conn, "x2", r, "A", at=datetime(2024, 11, 12, 9, 41), source="demo")
    # two demo "yes" on a3 would flip it to confirmed if they counted
    ans(conn, "x3", ids["a3"], "B", "yes", datetime(2024, 11, 13, 10, 5), source="demo")
    ans(conn, "x4", ids["a3"], "B", "yes", datetime(2024, 11, 13, 10, 6), source="demo")
    # a demo missed-flood report pair, a spam pair and a simulated sensor reading above the threshold
    ans(conn, "y1", None, "A", "report", datetime(2024, 11, 26, 9, 0), source="demo")
    ans(conn, "y2", None, "A", "report", datetime(2024, 11, 26, 9, 5), source="demo")
    ans(conn, "z1", None, "B", "report", datetime(2024, 11, 27, 9, 0), review_status="spam")
    ans(conn, "z2", None, "B", "report", datetime(2024, 11, 27, 9, 5), review_status="spam")
    repo.insert_sensor_reading(conn, "sim-1", datetime(2024, 11, 13, 10, 10), 99.0, True)
    repo.insert_sensor_reading(conn, "sim-1", datetime(2024, 11, 12, 9, 35), 99.0, True)
    assert run(conn, readings, events) == before


def test_real_sensor_reading_does_confirm(conn, readings, events, monkeypatch):
    ids = seed(conn)
    monkeypatch.setattr(repo, "sensor_devices", lambda: {"real-1": {"B"}})
    repo.insert_sensor_reading(conn, "real-1", datetime(2024, 11, 13, 10, 10), 99.0, False)
    k = run(conn, readings, events)["kpis"]
    assert (k["confirmed"], k["not_confirmed"]) == (3, 0) and ids


def test_empty_period_is_zeroes_and_null_lead(conn):
    s = statistics.stats(conn, FROM, TO)
    assert s["kpis"] == {"alerts": 0, "confirmed": 0, "not_confirmed": 0, "unverified": 0, "confirmation_rate": 0,
                         "missed_floods": 0, "median_lead_min": None}
    assert s["by_week"] == s["by_street"] == s["rain_at_onset"] == s["station_health"] == []
    assert s["sources"] == {"outcomes_from_news": 0, "outcomes_from_residents": 0}


def test_period_validation(conn):
    with pytest.raises(ValueError):
        statistics.stats(conn, TO, FROM)


def test_no_lead_without_an_earlier_alert(conn, events):
    add_alert(conn, "C", Level.WARNING, datetime(2024, 11, 20, 10, 0))      # after the 09:30 onset
    k = statistics.stats(conn, FROM, TO, events=events)["kpis"]
    assert k["median_lead_min"] is None


# ---------- station health ----------

def test_station_health_blanked_gauge_is_stale():
    stations = pd.DataFrame([{"graph_id": "26558", "kind": "wl", "name": "Kg. Perepat"},
                             {"graph_id": "26558", "kind": "rf", "name": "Kg. Perepat"},
                             {"graph_id": "PEKANMERU", "kind": "wl", "name": "Pekan Meru"}])
    day = slots(datetime(2024, 11, 12), datetime(2024, 11, 12, 23, 45))
    rows = [("26558", "wl", t, np.nan, np.nan) for t in day] + [("26558", "rf", t, 0.0, np.nan) for t in day]
    rows += [("PEKANMERU", "wl", t, np.nan, 1.0) for t in day[:48]]                 # half a day of data
    readings = pd.DataFrame(rows, columns=["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"])
    health = statistics.station_health(readings, stations, date(2024, 11, 12), date(2024, 11, 12))
    by = {h["graph_id"]: h for h in health}
    assert by["26558"] == {"graph_id": "26558", "name": "Kg. Perepat", "stale_pct": 1.0}
    assert by["PEKANMERU"]["stale_pct"] == 0.5
    assert health[0]["graph_id"] == "26558"                                          # worst first


def test_station_health_station_with_no_rows_at_all_is_fully_stale():
    stations = pd.DataFrame([{"graph_id": "S1", "kind": "rf", "name": "Silent"}])
    readings = pd.DataFrame(columns=["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"])
    [h] = statistics.station_health(readings, stations, date(2024, 11, 12), date(2024, 11, 12))
    assert h["stale_pct"] == 1.0


# ---------- episodes ----------

def flap(conn, street, minutes_alert_clear, level=Level.WATCH):
    """minutes_alert_clear: list of (kind, minute offset from 08:00 on 2024-11-05)."""
    base = datetime(2024, 11, 5, 8, 0)
    for kind, m in minutes_alert_clear:
        add_alert(conn, street, level if kind == "alert" else Level.NORMAL, base + timedelta(minutes=m), kind=kind)


def test_flapping_inside_the_cooldown_is_one_episode(conn):
    # 4 alert rows and 3 all-clears in 2 hours, every gap shorter than cooldown_min (60)
    flap(conn, "A", [("alert", 0), ("all_clear", 15), ("alert", 30), ("all_clear", 45), ("alert", 60),
                     ("all_clear", 75), ("alert", 105)])
    k = statistics.stats(conn, FROM, TO)["kpis"]
    x = statistics.analyse(conn, FROM, TO)[2]
    assert x["alert_rows"] == 4 and k["alerts"] == 1 and k["unverified"] == 1
    assert x["street_days_with_alert"] == 1 and x["by_level"]["watch"] == 1


def test_a_gap_longer_than_the_cooldown_starts_a_new_episode(conn):
    flap(conn, "A", [("alert", 0), ("all_clear", 15), ("alert", 30), ("all_clear", 45), ("alert", 45 + 61)])
    assert statistics.stats(conn, FROM, TO)["kpis"]["alerts"] == 2


def test_episode_level_is_the_highest_and_streets_are_separate(conn):
    add_alert(conn, "A", Level.WATCH, datetime(2024, 11, 5, 8, 0))
    add_alert(conn, "A", Level.DANGER, datetime(2024, 11, 5, 8, 30))
    add_alert(conn, "B", Level.WARNING, datetime(2024, 11, 5, 8, 10))
    assert statistics.stats(conn, FROM, TO)["kpis"]["alerts"] == 2
    assert statistics.analyse(conn, FROM, TO)[2]["by_level"] == {"watch": 0, "warning": 1, "danger": 1}


def test_an_episode_is_confirmed_if_any_row_is_and_counts_once(conn):
    a1 = add_alert(conn, "A", Level.WATCH, datetime(2024, 11, 5, 8, 0))
    add_alert(conn, "A", Level.NORMAL, datetime(2024, 11, 5, 8, 15), kind="all_clear")
    add_alert(conn, "A", Level.WATCH, datetime(2024, 11, 5, 8, 30))
    ans(conn, "d1", a1, "A", at=datetime(2024, 11, 5, 8, 20))
    ans(conn, "d2", a1, "A", at=datetime(2024, 11, 5, 8, 21))
    k = statistics.stats(conn, FROM, TO)["kpis"]
    assert (k["alerts"], k["confirmed"], k["unverified"], k["confirmation_rate"]) == (1, 1, 0, 1.0)


def test_open_episode_continues_while_rows_keep_coming_but_splits_after_48h_of_silence(conn):
    add_alert(conn, "A", Level.WATCH, datetime(2024, 11, 5, 8, 0))
    add_alert(conn, "A", Level.WARNING, datetime(2024, 11, 6, 20, 0))       # 36 h later, no all-clear: same episode
    assert statistics.stats(conn, FROM, TO)["kpis"]["alerts"] == 1
    add_alert(conn, "A", Level.WARNING, datetime(2024, 11, 20, 8, 0))       # 13+ days of silence: a new one
    assert statistics.stats(conn, FROM, TO)["kpis"]["alerts"] == 2


def test_two_confirmed_floods_weeks_apart_are_two_episodes(conn):
    a1 = add_alert(conn, "A", Level.WARNING, datetime(2024, 11, 5, 8, 0))
    a2 = add_alert(conn, "A", Level.WARNING, datetime(2024, 11, 20, 8, 0))
    for d in ("d1", "d2"):
        ans(conn, d, a1, "A", at=datetime(2024, 11, 5, 8, 30))
        ans(conn, d + "x", a2, "A", at=datetime(2024, 11, 20, 8, 30))
    k = statistics.stats(conn, FROM, TO)["kpis"]
    assert (k["alerts"], k["confirmed"]) == (2, 2)


def test_episode_across_the_month_edge_keeps_its_level_and_outcome_and_counts_once(conn):
    add_alert(conn, "A", Level.WATCH, datetime(2024, 10, 31, 23, 30))
    a2 = add_alert(conn, "A", Level.DANGER, datetime(2024, 11, 1, 0, 30))
    ans(conn, "d1", a2, "A", at=datetime(2024, 11, 1, 0, 45))
    ans(conn, "d2", a2, "A", at=datetime(2024, 11, 1, 0, 50))
    oct_, oct_f, oct_x = statistics.analyse(conn, date(2024, 10, 1), date(2024, 10, 31))
    nov, nov_f, nov_x = statistics.analyse(conn, date(2024, 11, 1), date(2024, 11, 30))
    assert (oct_["kpis"]["alerts"], oct_["kpis"]["confirmed"], oct_x["by_level"]["danger"]) == (1, 1, 1)
    assert nov["kpis"]["alerts"] == 0                                      # started in October: not counted twice
    assert [f["date"] for f in nov_f] == [date(2024, 11, 1)] and oct_f == []   # the confirmed row's own date


def test_a_long_open_episode_is_not_split_by_the_lookback(conn):
    # rows every 30 h for 6 days with no all-clear: one episode, even when the period starts in the middle
    for h in range(0, 150, 30):
        add_alert(conn, "A", Level.WATCH, datetime(2024, 11, 1, 6, 0) + timedelta(hours=h))
    assert statistics.stats(conn, date(2024, 11, 1), date(2024, 11, 30))["kpis"]["alerts"] == 1
    assert statistics.stats(conn, date(2024, 11, 4), date(2024, 11, 30))["kpis"]["alerts"] == 0


# ---------- Outlook rows ----------

def outlook(conn, streets, at, kind="alert"):
    rows = [Alert(s, Level.WATCH if kind == "alert" else Level.NORMAL, kind, at, at + timedelta(hours=6),
                  at + timedelta(hours=12), (Reason("forecast_rain", 45.0, "mm", None, "Forecast", "Ramalan"),), ("outlook",))
            for s in streets]
    repo.insert_alerts(conn, rows, is_replay=False, is_backfill=False, horizon="outlook")


def test_outlook_rows_and_their_all_clears_change_nothing(conn, readings, events):
    seed(conn)
    before = run(conn, readings, events)
    outlook(conn, ["A", "B", "C", "D"], datetime(2024, 11, 12, 4, 0))              # 5 h before A's nowcast Warning
    outlook(conn, ["A", "B", "C", "D"], datetime(2024, 11, 12, 9, 5), kind="all_clear")   # would close A's episode
    outlook(conn, [f"S{i}" for i in range(50)], datetime(2024, 11, 6, 15, 0))
    assert run(conn, readings, events) == before
    assert statistics.analyse(conn, FROM, TO, street_names=NAMES, events=events)[2]["alert_rows"] == 4


# ---------- floods over midnight, news ----------

def test_a_news_flood_just_after_midnight_and_its_confirmed_alert_are_one_flood(conn):
    a = add_alert(conn, "C", Level.WARNING, datetime(2024, 11, 20, 23, 30))
    ans(conn, "d1", a, "C", at=datetime(2024, 11, 20, 23, 50))
    ans(conn, "d2", a, "C", at=datetime(2024, 11, 20, 23, 55))
    ev = pd.DataFrame([{"event_id": "e", "street_id": "C", "start_time_local": "2024-11-21 00:10", "date_precision": "hour",
                        "flooded": 1, "checked_by": "T", "status": "checked"}])
    s, floods, _ = statistics.analyse(conn, FROM, TO, events=ev)
    assert len(floods) == 1 and s["by_street"][0]["floods"] == 1


def test_unchecked_draft_events_confirm_nothing(conn, events):
    seed(conn)
    drafts = events.assign(checked_by=None, status="draft")
    k = statistics.stats(conn, FROM, TO, events=drafts)["kpis"]
    assert k["confirmed"] == 1 and k["median_lead_min"] == 40.0            # C is no longer confirmed by news


def test_episodes_function_merge_rule():
    rows = [{"street_id": "A", "kind": k, "level": lv, "issued_at": datetime(2024, 11, 5, 8, 0) + timedelta(minutes=m),
             "alert_id": f"{k}{m}", "outcome": "unverified"}
            for k, lv, m in (("alert", "watch", 0), ("all_clear", "normal", 10), ("alert", "watch", 70),
                             ("all_clear", "normal", 80), ("alert", "warning", 140))]
    assert len(episodes_mod.episodes(rows, timedelta(minutes=60))) == 1       # 60 min after the first all-clear: merged
    assert len(episodes_mod.episodes(rows, timedelta(minutes=59))) == 3


def test_mixed_area_and_street_events_do_not_crash(conn):
    ev = pd.DataFrame([
        {"event_id": "area", "street_ids": None, "event_date": "2024-11-12", "date_precision": "day", "flooded": 1,
         "sdp_township": "Town", "checked_by": "T", "status": "checked"},
        {"event_id": "st", "street_ids": "C", "event_date": "2024-11-20", "start_time_local": "2024-11-20 09:30",
         "date_precision": "hour", "flooded": 1, "checked_by": "T", "status": "checked"}])
    s, floods, _ = statistics.analyse(conn, FROM, TO, street_names=NAMES, events=ev, township_name="Town")
    assert [f["street_id"] for f in floods] == ["C"] and s["by_street"][0]["floods"] == 1


def test_a_flood_over_the_period_edge_counts_in_one_period_only(conn):
    a = add_alert(conn, "A", Level.WARNING, datetime(2024, 10, 31, 23, 50))
    b = add_alert(conn, "A", Level.WARNING, datetime(2024, 11, 1, 0, 20))
    for aid in (a, b):
        ans(conn, f"d1{aid[-3:]}", aid, "A", at=datetime(2024, 11, 1, 0, 40))
        ans(conn, f"d2{aid[-3:]}", aid, "A", at=datetime(2024, 11, 1, 0, 41))
    october = statistics.analyse(conn, date(2024, 10, 1), date(2024, 10, 31))[1]
    november = statistics.analyse(conn, date(2024, 11, 1), date(2024, 11, 30))[1]
    assert len(october) == 1 and november == []
