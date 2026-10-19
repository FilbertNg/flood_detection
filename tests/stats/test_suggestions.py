from datetime import date, datetime, timedelta
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from floodready.db import repo, schema
from floodready.engine.types import Alert, Level, Reason
from floodready.stats import suggestions as sug

FROM, TO = date(2024, 11, 1), date(2024, 11, 30)
END = "Screening suggestion; site survey needed."


@pytest.fixture
def conn():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        yield c


def alert(street, at, level=Level.WARNING, kind="alert"):
    return Alert(street, level, kind, at, at, at + timedelta(hours=1),
                 (Reason("rain_1h", 60.0, "mm", "1", "Heavy rain", "Hujan lebat"),), ("rule_rain",))


def add(conn, street, at, level=Level.WARNING, *, replay=False, backfill=True, horizon="nowcast"):
    return repo.insert_alerts(conn, [alert(street, at, level)], is_replay=replay, is_backfill=backfill, horizon=horizon)[0]


def episode(conn, street, at, level=Level.WARNING, hours=1):
    """One alert followed by its all-clear `hours` later (backfill rows)."""
    add(conn, street, at, level)
    repo.insert_alerts(conn, [alert(street, at + timedelta(hours=hours), Level.NORMAL, "all_clear")], is_replay=False, is_backfill=True)


def confirm(conn, aid, street, at, source="resident", n=2, depth=None):
    for i in range(n):
        repo.insert_answer(conn, {"device_id": f"{aid[-12:]}-{i}", "alert_id": aid, "street_id": street, "answer": "yes",
                                  "answered_at": at + timedelta(minutes=10 + i), "source": source, "depth": depth})


def flood(conn, street, at, **kw):
    """A confirmed (by two residents) alert."""
    aid = add(conn, street, at, backfill=False)
    confirm(conn, aid, street, at, **kw)
    return aid


def streets(rows):
    """rows: (street_id, name, susceptibility, x_offset_m). Streets are 100 m east-west lines, x metres apart."""
    geoms, recs = [], []
    deg = 111_320 * np.cos(np.radians(3.1))
    for sid, name, susc, x in rows:
        lon0 = 101.40 + x / deg
        geoms.append(LineString([(lon0, 3.1), (lon0 + 100 / deg, 3.1)]))
        recs.append({"street_id": sid, "name": name, "susceptibility": susc, "centroid_lat": 3.1,
                     "centroid_lon": lon0 + 50 / deg})
    return gpd.GeoDataFrame(recs, geometry=geoms, crs="EPSG:4326")


def tide_table():
    times = pd.date_range("2023-10-01", "2024-12-31 23:00", freq="h")
    # high water at 00:00 and 12:00 every day
    rel = ((12 - (times.hour % 12)) % 12).astype(float)
    rel = np.where(rel > 6, rel - 12, rel)
    return pd.DataFrame({"time_local": times, "tide_height_m": 0.0, "hours_to_high_tide": rel})


A = streets([("BBR-a", "Jalan A", 5, 0)])
NO_HEALTH: list[dict] = []


def run(conn, st=A, health=NO_HEALTH, **kw):
    return sug.suggestions(conn, FROM, TO, tide_table(), health, streets=st, **kw)


def rules(out):
    return sorted({s["rule"] for s in out})


def test_empty_database_fires_nothing(conn):
    assert run(conn) == []


def test_sug1_drainage_capacity(conn):
    for d in (3, 10, 17):
        flood(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    # onset = the first resident observation (yes at +10 min), not the alert time
    rain = {datetime(2024, 11, 3, 6, 10): 35.0, datetime(2024, 11, 10, 6, 10): 42.0, datetime(2024, 11, 17, 6, 10): 48.0}
    out = run(conn, onset_rain=lambda s, at: rain.get(at))
    assert rules(out) == ["SUG-1"]
    s = out[0]
    assert s["priority"] == "medium" and s["street_id"] == "BBR-a" and s["street_name"] == "Jalan A"     # no knee depth reported
    assert s["evidence"]["max_depth"] is None
    assert s["evidence"]["rain_at_onset_mm"] == [35.0, 42.0, 48.0]
    assert s["evidence"]["flood_dates"] == ["2024-11-03", "2024-11-10", "2024-11-17"]
    assert "drainage capacity review" in s["text"] and "Jalan A" in s["text"] and s["text"].endswith(END)
    assert s["status"] == "open" and s["note"] is None


def test_sug1_priority_high_when_a_confirming_answer_is_knee_deep(conn):
    for d, depth in ((3, "ankle"), (10, "knee"), (17, None)):
        aid = add(conn, "BBR-a", datetime(2024, 11, d, 6, 0), backfill=False)
        confirm(conn, aid, "BBR-a", datetime(2024, 11, d, 6, 0), depth=depth)
    [s] = run(conn, onset_rain=lambda st, at: 40.0)
    assert s["rule"] == "SUG-1" and s["priority"] == "high" and s["evidence"]["max_depth"] == "knee"


def test_sug1_flood_onset_is_the_first_observation_and_a_sensor_counts(conn):
    dev, thr = next(iter(repo.sensor_devices())), repo.sensor_threshold_cm()
    street = sorted(repo.sensor_devices()[dev])[0]
    for d in (3, 10, 17):
        add(conn, street, datetime(2024, 11, d, 6, 0), backfill=False)
        repo.insert_sensor_reading(conn, dev, datetime(2024, 11, d, 6, 40), thr + 5, simulated=False)
    seen = []
    sug.suggestions(conn, FROM, TO, tide_table(), [], streets=streets([(street, "S", 5, 0)]),
                    onset_rain=lambda st, at: seen.append(at) or 30.0)
    assert max(seen) == datetime(2024, 11, 17, 6, 40)
    assert {datetime(2024, 11, d, 6, 40) for d in (3, 10, 17)} <= set(seen)     # every window ends at or before the onset
    assert all(t.time() <= datetime(2024, 1, 1, 6, 40).time() for t in seen)


def test_sug1_late_yes_does_not_hide_the_storm_rain(conn):
    t = pd.date_range("2024-11-01", "2024-11-30 23:45", freq="15min")
    mm = np.where((t.day.isin([3, 10, 17])) & (t.hour >= 6) & ((t.hour < 8) | ((t.hour == 8) & (t.minute <= 45))), 6.0, 0.0)
    rd = pd.DataFrame({"graph_id": "G1", "kind": "rf", "time_local": t, "rain_15min_mm": mm, "wl_m": np.nan})
    fn = sug.onset_rain_from_archive(rd, {"BBR-a": {"rf": ["G1"]}})
    for d in (3, 10, 17):                       # 72 mm fell 06:00-08:45; alert 09:00; first yes only at 11:30
        aid = add(conn, "BBR-a", datetime(2024, 11, d, 9, 0), backfill=False)
        for i in range(2):
            repo.insert_answer(conn, {"device_id": f"late-{d}-{i}", "alert_id": aid, "street_id": "BBR-a", "answer": "yes",
                                      "answered_at": datetime(2024, 11, d, 11, 30 + i)})
    assert fn("BBR-a", datetime(2024, 11, 3, 11, 30)) == 30.0               # the window at the answer alone misses most of it
    assert run(conn, onset_rain=fn) == []                                    # so SUG-1 must not claim "less rain than the guide"


def test_sug1_near_misses(conn):
    for d in (3, 10, 17):
        flood(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    assert run(conn, onset_rain=lambda s, at: 61.0) == []                      # median not below the guide
    assert run(conn, onset_rain=lambda s, at: None) == []                      # no rain data: never guess
    assert run(conn) == []                                                     # no rain source at all


def test_sug1_needs_three_floods(conn):
    for d in (3, 10):
        flood(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    assert run(conn, onset_rain=lambda s, at: 30.0) == []


def test_sug2_tidal_backflow(conn):
    for d in (3, 10, 17):
        flood(conn, "BBR-a", datetime(2024, 11, d, 12, 30))     # 0.5 h after high water
    out = run(conn)
    assert rules(out) == ["SUG-2"]
    assert out[0]["priority"] == "medium" and "flap gates" in out[0]["text"] and out[0]["text"].endswith(END)
    assert out[0]["evidence"]["share_near_high_tide"] == 1.0
    assert out[0]["evidence"]["flood_dates"] == ["2024-11-03", "2024-11-10", "2024-11-17"]


def news_frame(homes):
    return pd.DataFrame({"event_id": [f"E{d}" for d in (3, 10, 17)], "street_ids": ["BBR-a"] * 3, "flooded": ["1"] * 3,
                         "date_precision": ["hour"] * 3, "status": ["checked"] * 3, "checked_by": ["x"] * 3,
                         "homes_affected": homes, "event_date": [f"2024-11-{d:02d}" for d in (3, 10, 17)],
                         "start_time_local": [f"2024-11-{d:02d} 13:00" for d in (3, 10, 17)]})


def test_sug2_priority_high_when_news_reports_homes_affected(conn):
    for d in (3, 10, 17):
        add(conn, "BBR-a", datetime(2024, 11, d, 12, 30))
    [s] = run(conn, events=news_frame(["12", "", "0"]))
    assert s["rule"] == "SUG-2" and s["priority"] == "high" and s["evidence"]["homes_affected"] is True
    assert run(conn, events=news_frame(["", "", "0"]))[0]["priority"] == "medium"


def test_sug2_below_seventy_percent(conn):
    for d, h in ((3, 12), (10, 12), (17, 6)):                   # 2 of 3 = 67%
        flood(conn, "BBR-a", datetime(2024, 11, d, h, 30))
    assert run(conn) == []
    flood(conn, "BBR-b", datetime(2024, 11, 5, 12, 30))         # a single flood is never enough
    assert run(conn, st=streets([("BBR-a", "A", 5, 0), ("BBR-b", "B", 5, 5000)])) == []


def test_sug3_neighbour_comparison(conn):
    st = streets([("BBR-a", "Jalan A", 3, 0)] + [(f"BBR-n{i}", f"N{i}", 3, 100 + 100 * i) for i in range(3)]
                 + [("BBR-far", "Far", 3, 3000)])
    for d in (3, 17):
        flood(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    out = run(conn, st=st)
    assert rules(out) == ["SUG-3"]
    assert out[0]["priority"] == "medium" and out[0]["text"].endswith(END) and "Inspect and clear drains" in out[0]["text"]
    assert out[0]["evidence"]["neighbours_without_floods"] == 3


def test_sug3_not_when_a_neighbour_floods_too(conn):
    st = streets([("BBR-a", "A", 3, 0)] + [(f"BBR-n{i}", f"N{i}", 3, 100 + 100 * i) for i in range(3)])
    for d in (3, 17):
        flood(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    flood(conn, "BBR-n0", datetime(2024, 11, 3, 6, 0))
    assert run(conn, st=st) == []


def test_sug3_year_on_year(conn):
    flood(conn, "BBR-a", datetime(2023, 11, 8, 6, 0))
    for d in (3, 17):
        flood(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    out = run(conn)
    assert rules(out) == ["SUG-3"]
    assert out[0]["evidence"]["floods_this_period"] == 2 and out[0]["evidence"]["floods_same_period_last_year"] == 1


def test_sug3_year_on_year_needs_last_year_data(conn):
    for d in (3, 17):
        flood(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    assert run(conn) == []                                                    # 0 last year may just be "no data"


def cluster_streets():
    return streets([("BBR-a", "Jalan A", 5, 0), ("BBR-b", "Jalan B", 4, 110), ("BBR-c", "Jalan C", 5, 220),
                    ("BBR-d", "Jalan D", 5, 9000)])


def test_sug4_cluster(conn):
    for s in ("BBR-a", "BBR-b", "BBR-c"):
        for d in (3, 17):
            flood(conn, s, datetime(2024, 11, d, 6, 0))
    out = run(conn, st=cluster_streets())
    assert rules(out) == ["SUG-4"]
    assert len(out) == 1 and out[0]["priority"] == "medium" and out[0]["text"].endswith(END)
    assert out[0]["evidence"]["street_ids"] == ["BBR-a", "BBR-b", "BBR-c"]
    assert out[0]["evidence"]["total_flood_days"] == 6
    assert "retention" in out[0]["text"]


def test_sug4_needs_adjacency_susceptibility_and_repeats(conn):
    for s in ("BBR-a", "BBR-c", "BBR-d"):                       # d is far away
        for d in (3, 17):
            flood(conn, s, datetime(2024, 11, d, 6, 0))
    assert run(conn, st=cluster_streets()) == []
    st = streets([("BBR-a", "A", 5, 0), ("BBR-b", "B", 3, 110), ("BBR-c", "C", 5, 220)])       # b only susceptibility 3
    for d in (3, 17):
        flood(conn, "BBR-b", datetime(2024, 11, d, 6, 0))
    assert run(conn, st=st) == []


def test_sug5_pre_event_readiness_from_backfill_alone(conn):
    for d in range(1, 6):
        episode(conn, "BBR-a", datetime(2024, 11, d, 6, 0), Level.WARNING if d % 2 else Level.DANGER)
    out = run(conn)
    assert rules(out) == ["SUG-5"]
    assert out[0]["priority"] == "medium" and out[0]["evidence"]["alert_count"] == 5
    assert len(out[0]["evidence"]["episode_dates"]) == 5 and "flood_dates" not in out[0]["evidence"]
    assert out[0]["text"].endswith(END)
    assert "pre-storm" in out[0]["text"]


def test_sug5_flapping_counts_as_one_episode(conn):
    for k in range(40):                      # 40 alert/all-clear cycles 20 min apart on one night: ONE episode
        episode(conn, "BBR-a", datetime(2024, 11, 2, 0, 0) + timedelta(minutes=80 * k), Level.WARNING, hours=1)
    assert run(conn) == []
    for d in range(10, 14):                  # + 4 more separate episodes = 5 episodes in all
        episode(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    out = run(conn)
    assert rules(out) == ["SUG-5"]
    assert out[0]["evidence"]["episodes"] == 5 and out[0]["evidence"]["raw_alert_rows"] == 44


def test_sug5_near_miss_and_watch_does_not_count(conn):
    for d in range(1, 5):
        episode(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    for d in range(5, 9):
        episode(conn, "BBR-a", datetime(2024, 11, d, 6, 0), Level.WATCH)
    assert run(conn) == []


def test_sug5_watch_escalating_to_warning_is_one_warning_episode(conn):
    for d in range(1, 6):
        at = datetime(2024, 11, d, 6, 0)
        add(conn, "BBR-a", at, Level.WATCH)
        add(conn, "BBR-a", at + timedelta(minutes=30), Level.WARNING)
        repo.insert_alerts(conn, [alert("BBR-a", at + timedelta(hours=2), Level.NORMAL, "all_clear")],
                           is_replay=False, is_backfill=True)
    assert run(conn)[0]["evidence"]["episodes"] == 5


def sug5_streets(spec):
    """spec: {street: (episodes, danger_episodes, susceptibility)}"""
    for sid, (n, danger, _) in spec.items():
        for k in range(n):
            episode(conn_holder[0], sid, datetime(2024, 11, 1 + k, 6, 0), Level.DANGER if k < danger else Level.WARNING)
    return streets([(sid, sid, susc_, i * 1000) for i, (sid, (_, _, susc_)) in enumerate(spec.items())])


conn_holder: list = []


def test_sug5_is_capped_and_ranked(conn):
    conn_holder[:] = [conn]
    st = sug5_streets({"BBR-e": (5, 0, 5), "BBR-d": (6, 0, 1), "BBR-c": (5, 2, 1), "BBR-b": (5, 0, 3),
                       "BBR-a": (5, 0, 3), "BBR-low": (4, 4, 5)})
    out = sug.suggestions(conn, FROM, TO, tide_table(), [], streets=st, sug5_top_n=4,
                          street_stations={s: {"wl": "PEKANMERU"} for s in ("BBR-a", "BBR-b", "BBR-c", "BBR-d", "BBR-e")},
                          station_names={"PEKANMERU": "Pekan Meru"})
    got = sorted(out, key=lambda s: s["evidence"]["rank"])
    # episodes, then Danger episodes, then susceptibility, then street_id; BBR-low has only 4 episodes: not eligible
    assert [s["street_id"] for s in got] == ["BBR-d", "BBR-c", "BBR-e", "BBR-a"]
    assert [s["evidence"]["rank"] for s in got] == [1, 2, 3, 4]
    assert all(s["evidence"]["eligible_streets"] == 5 for s in got)
    ev = got[0]["evidence"]
    assert ev["river_station_name"] == "Pekan Meru" and ev["eligible_streets_on_same_river_station"] == 5
    assert "Rank 1 of 5 eligible streets" in ev["notes"] and "Pekan Meru" in ev["notes"]


def test_sug5_cap_defaults_to_config(conn):
    conn_holder[:] = [conn]
    st = sug5_streets({f"BBR-s{i:02d}": (5, 0, 3) for i in range(15)})
    out = sug.suggestions(conn, FROM, TO, tide_table(), [], streets=st)
    assert len(out) == 10 and {s["evidence"]["eligible_streets"] for s in out} == {15}
    assert sorted(s["street_id"] for s in out) == [f"BBR-s{i:02d}" for i in range(10)]     # full tie: street_id order


def test_sug5_outside_period_is_ignored(conn):
    for d in range(1, 6):
        episode(conn, "BBR-a", datetime(2024, 12, d, 6, 0))
    assert run(conn) == []


def report(conn, device, street, at, photo=None, source="resident"):
    repo.insert_answer(conn, {"device_id": device, "alert_id": None, "street_id": street, "answer": "report",
                              "answered_at": at, "photo_path": photo, "source": source})


def test_sug6_monitoring_gap(conn):
    for day in (4, 20):
        report(conn, f"d1-{day}", "BBR-a", datetime(2024, 11, day, 10, 0))
        report(conn, f"d2-{day}", "BBR-a", datetime(2024, 11, day, 10, 20))
    out = run(conn)
    assert rules(out) == ["SUG-6"]
    assert out[0]["priority"] == "low" and out[0]["evidence"]["missed_floods"] == 2
    assert out[0]["text"].endswith(END) and "under-predicts" in out[0]["text"]


def test_sug6_one_missed_flood_or_covered_by_alert_or_demo(conn):
    report(conn, "d1", "BBR-a", datetime(2024, 11, 4, 10, 0))
    report(conn, "d2", "BBR-a", datetime(2024, 11, 4, 10, 20))
    assert run(conn) == []
    add(conn, "BBR-a", datetime(2024, 11, 20, 9, 0))                         # warning active when reported
    for dev in ("e1", "e2"):
        report(conn, dev, "BBR-a", datetime(2024, 11, 20, 10, 0))
    for dev in ("x1", "x2"):
        report(conn, dev, "BBR-a", datetime(2024, 11, 25, 10, 0), source="demo")
    assert run(conn) == []


def health(stale):
    return [{"graph_id": "26558", "name": "Kg. Perepat, Kapar", "stale_pct": stale}]


def test_sug7_data_health(conn):
    out = run(conn, health=health(0.873))
    assert rules(out) == ["SUG-7"]
    s = out[0]
    assert s["priority"] == "low" and s["street_id"] == "station:26558" and s["street_name"] == "Kg. Perepat, Kapar"
    assert s["evidence"]["stale_pct"] == 0.873 and s["text"].endswith(END) and "87%" in s["text"]
    assert "backup station" in s["text"]


def test_sug7_threshold_is_strictly_above_ten_percent(conn):
    assert run(conn, health=health(0.10)) == []
    assert run(conn, health=health(0.0)) == []
    assert rules(run(conn, health=health(0.105))) == ["SUG-7"]


def test_replay_demo_and_simulated_rows_never_count(conn):
    for d in range(1, 8):                                                    # 7 replay warnings (each with an all-clear)
        add(conn, "BBR-a", datetime(2024, 11, d, 6, 0), replay=True, backfill=False)
        repo.insert_alerts(conn, [alert("BBR-a", datetime(2024, 11, d, 7, 0), Level.NORMAL, "all_clear")], is_replay=True, is_backfill=False)
    for d in (3, 10, 17):                                                    # alerts "confirmed" only by demo answers
        aid = add(conn, "BBR-a", datetime(2024, 11, d, 12, 30), backfill=False)
        confirm(conn, aid, "BBR-a", datetime(2024, 11, d, 12, 30), source="demo")
    dev, thr = next(iter(repo.sensor_devices())), repo.sensor_threshold_cm()
    for d in (3, 10, 17):                                                    # simulated sensor above threshold
        repo.insert_sensor_reading(conn, dev, datetime(2024, 11, d, 12, 40), thr + 20, simulated=True)
    street = sorted(repo.sensor_devices()[dev])[0]
    for d in (3, 10, 17):
        add(conn, street, datetime(2024, 11, d, 12, 30), backfill=False)
    out = sug.suggestions(conn, FROM, TO, tide_table(), [],
                          streets=streets([("BBR-a", "A", 5, 0), (street, "S", 5, 5000)]), onset_rain=lambda s, at: 10.0)
    assert out == []


def test_real_sensor_confirms(conn):
    dev, thr = next(iter(repo.sensor_devices())), repo.sensor_threshold_cm()
    street = sorted(repo.sensor_devices()[dev])[0]
    st = streets([(street, "Sensor street", 5, 0)])
    for d in (3, 10, 17):
        add(conn, street, datetime(2024, 11, d, 12, 30), backfill=False)
        repo.insert_sensor_reading(conn, dev, datetime(2024, 11, d, 12, 40), thr + 5, simulated=False)
    assert rules(sug.suggestions(conn, FROM, TO, tide_table(), [], streets=st)) == ["SUG-2"]


def test_news_outcomes_confirm_backfill_alerts(conn):
    for d in (3, 10, 17):
        add(conn, "BBR-a", datetime(2024, 11, d, 12, 30))
    ev = news_frame(["", "", ""])
    assert rules(run(conn, events=ev)) == ["SUG-2"]
    assert run(conn) == []
    assert run(conn, events=ev.assign(status="draft", checked_by="")) == []        # unchecked drafts never confirm


def test_real_pr43_rows_confirm_nothing_but_checked_copies_do(conn):
    raw = pd.read_csv(Path(__file__).resolve().parents[1] / "fixtures" / "events_wp6_pr43.csv", dtype=str)
    assert set(raw["status"]) == {"draft"}
    for d in (3, 10, 17):
        add(conn, "BBR-a", datetime(2024, 11, d, 12, 30))
    assert run(conn, events=raw) == []
    base = raw.iloc[:3].copy()                                  # the same rows marked checked, in test data only
    base["status"], base["checked_by"] = "checked", "tester"
    base["street_ids"], base["flooded"], base["date_precision"] = "BBR-a", "1", "hour"
    base["start_time_local"] = [f"2024-11-{d:02d} 13:00" for d in (3, 10, 17)]
    base["event_date"] = [f"2024-11-{d:02d}" for d in (3, 10, 17)]
    assert rules(run(conn, events=base)) == ["SUG-2"]


def test_ids_stable_and_short(conn):
    long_street = "BBR-" + "very-long-street-name-" * 3 + "x"
    for d in range(1, 6):
        episode(conn, long_street, datetime(2024, 11, d, 6, 0))
    st = streets([(long_street, "Long", 3, 0)])
    one, two = run(conn, st=st), run(conn, st=st)
    assert [s["id"] for s in one] == [s["id"] for s in two]
    assert one[0]["id"].startswith("s_sug5_") and len(one[0]["id"]) <= 40
    assert one[0]["id"].endswith("_241101-241130")
    assert sug.suggestions(conn, date(2024, 10, 1), date(2024, 10, 31), tide_table(), [], streets=st) == []


def test_short_street_id_is_readable_in_the_id(conn):
    for d in range(1, 6):
        episode(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    assert run(conn)[0]["id"] == "s_sug5_BBR-a_241101-241130"


def test_unknown_street_name_falls_back_to_id(conn):
    for d in range(1, 6):
        episode(conn, "BBR-zzz", datetime(2024, 11, d, 6, 0))
    assert run(conn)[0]["street_name"] == "BBR-zzz"


def test_upsert_keeps_status_and_note(conn):
    for d in range(1, 6):
        episode(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
    first = run(conn)
    sug.save(conn, first, FROM, TO)
    repo.update_suggestion(conn, first[0]["id"], "accepted", "will do")
    sug.save(conn, run(conn), FROM, TO)
    rows = list(conn.execute(schema.suggestions.select()))
    assert len(rows) == 1 and rows[0].status == "accepted" and rows[0].note == "will do"
    assert rows[0].period_from == FROM and rows[0].period_to == TO


def test_outlook_all_clear_does_not_split_a_nowcast_episode(conn):
    for d in (2, 6, 10, 14, 18):                            # 5 storms, each ONE nowcast episode; the Outlook clears mid-storm
        base = datetime(2024, 11, d, 10, 0)
        add(conn, "BBR-a", base, Level.WARNING)
        add(conn, "BBR-a", base + timedelta(hours=2, minutes=30), Level.DANGER)
        repo.insert_alerts(conn, [alert("BBR-a", base + timedelta(hours=1), Level.NORMAL, "all_clear")],
                           is_replay=False, is_backfill=True, horizon="outlook")
        repo.insert_alerts(conn, [alert("BBR-a", base + timedelta(hours=4), Level.NORMAL, "all_clear")],
                           is_replay=False, is_backfill=True)
    [s] = run(conn)
    assert s["rule"] == "SUG-5" and s["evidence"]["episodes"] == 5 and s["evidence"]["raw_alert_rows"] == 10


def test_confirmed_outlook_row_is_not_a_flood_onset(conn):
    for d in (3, 10, 17):
        aid = add(conn, "BBR-a", datetime(2024, 11, d, 5, 0), Level.WATCH, backfill=False, horizon="outlook")
        confirm(conn, aid, "BBR-a", datetime(2024, 11, d, 5, 0))
    assert run(conn, onset_rain=lambda s, at: 5.0) == []


def test_save_removes_stale_open_rows_but_keeps_touched_ones(conn):
    for d in range(1, 6):
        episode(conn, "BBR-a", datetime(2024, 11, d, 6, 0))
        episode(conn, "BBR-b", datetime(2024, 11, d, 6, 0))
    st = streets([("BBR-a", "A", 5, 0), ("BBR-b", "B", 5, 5000)])
    first = run(conn, st=st)
    sug.save(conn, first, FROM, TO, township="BBR")
    ids = {s["street_id"]: s["id"] for s in first}
    repo.update_suggestion(conn, ids["BBR-b"], "accepted", None)
    conn.execute(schema.alerts.delete())
    sug.save(conn, run(conn, st=st), FROM, TO, township="BBR")          # nothing fires any more
    left = {r.street_id: r.status for r in conn.execute(schema.suggestions.select())}
    assert left == {"BBR-b": "accepted"}                                  # the open BBR-a row is gone, the touched one stays


def readings(station, kind, start, n, values=None, step=15):
    t = pd.date_range(start, periods=n, freq=f"{step}min")
    v = np.ones(n) if values is None else values
    return pd.DataFrame({"graph_id": station, "kind": kind, "time_local": t,
                         "rain_15min_mm": v if kind == "rf" else np.nan, "wl_m": v if kind == "wl" else np.nan})


def test_station_health_counts_blank_and_missing_time_as_stale():
    n = 10 * 96
    good = readings("G", "wl", "2024-11-01", n)
    dead = readings("D", "wl", "2024-11-01", n, np.where(np.arange(n) < 0.8 * n, np.nan, 1.0))   # 80% blanked by QC
    short = readings("S", "rf", "2024-11-01", n // 2)                                           # rows missing for the last half
    other = readings("R", "rf", "2024-11-01", n)                   # another rain gauge shows the archive runs to the end
    out = {h["graph_id"]: h for h in sug.station_health(pd.concat([good, dead, short, other]), date(2024, 11, 1),
                                                        date(2024, 11, 10), names={"D": "Dead gauge"})}
    assert out["G"]["stale_pct"] == 0.0
    assert out["D"]["stale_pct"] == 0.8 and out["D"]["name"] == "Dead gauge"
    assert out["S"]["stale_pct"] == 0.5 and out["S"]["name"] == "S"


def test_station_health_takes_worst_series_of_a_station():
    n = 96
    rf = readings("X", "rf", "2024-11-01", n)
    wl = readings("X", "wl", "2024-11-01", n, np.full(n, np.nan))
    [h] = sug.station_health(pd.concat([rf, wl]), date(2024, 11, 1), date(2024, 11, 1))
    assert h["stale_pct"] == 1.0


def test_station_health_empty_input():
    empty = pd.DataFrame(columns=["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"])
    assert sug.station_health(empty, date(2024, 11, 1), date(2024, 11, 2)) == []


def test_station_health_does_not_count_future_or_unarchived_slots():
    n = 5 * 96                                                      # the archive covers 1-5 Nov only
    good = readings("G", "rf", "2024-11-01", n)
    dead = readings("D", "wl", "2024-11-01", n, np.full(n, np.nan))
    by = {h["graph_id"]: h for h in sug.station_health(pd.concat([good, dead]), date(2024, 11, 1), date(2024, 11, 30),
                                                       detail=True)}
    assert by["G"]["stale_pct"] == 0.0 and by["D"]["stale_pct"] == 1.0
    assert by["G"]["covered_from"].startswith("2024-11-01T00:00") and by["G"]["covered_to"].startswith("2024-11-05T23:45")
    assert by["D"]["series"] == "wl" and by["G"]["series"] == "rf"


def test_station_health_wl_before_archive_start_is_not_stale():
    wl = readings("W", "wl", "2024-04-01", 96 * 10)                  # WL archive starts 1 Apr 2024
    rf = readings("W", "rf", "2024-01-01", 96 * 120)
    [h] = sug.station_health(pd.concat([wl, rf]), date(2024, 3, 1), date(2024, 4, 10), detail=True)
    assert h["stale_pct"] == 0.0


def test_station_health_series_with_no_covered_slot_is_skipped():
    assert sug.station_health(readings("W", "wl", "2024-12-01", 96), date(2024, 11, 1), date(2024, 11, 10)) == []


def test_station_health_default_shape_has_three_keys():
    [h] = sug.station_health(readings("X", "rf", "2024-11-01", 96), date(2024, 11, 1), date(2024, 11, 1))
    assert set(h) == {"graph_id", "name", "stale_pct"}


def test_sug7_text_names_the_stale_series(conn):
    wl = [{"graph_id": "26558", "name": "Kg. Perepat", "stale_pct": 0.7, "series": "wl",
           "covered_from": "2024-11-01T00:00:00", "covered_to": "2024-11-30T23:45:00"}]
    [s] = run(conn, health=wl)
    assert "in our archive" in s["text"] and "river level gauge" in s["text"] and "rain gauge" not in s["text"] and s["evidence"]["series"] == "wl"
    assert s["evidence"]["covered_to"] == "2024-11-30T23:45:00"
    [r] = run(conn, health=[{**wl[0], "series": "rf"}])
    assert "rain gauge" in r["text"]


def test_onset_rain_is_the_four_hour_total_ending_at_onset_without_look_ahead():
    t = pd.date_range("2024-11-12 03:00", "2024-11-12 09:00", freq="15min")
    rd = pd.DataFrame({"graph_id": "G1", "kind": "rf", "time_local": t, "rain_15min_mm": 1.0, "wl_m": np.nan})
    fn = sug.onset_rain_from_archive(rd, {"BBR-a": {"rf": ["G1"]}})
    assert fn("BBR-a", datetime(2024, 11, 12, 8, 0)) == 16.0           # (04:00, 08:00] = 16 slots
    assert fn("BBR-a", datetime(2024, 11, 12, 3, 30)) == 3.0           # nothing after the onset is used
    assert fn("BBR-zzz", datetime(2024, 11, 12, 8, 0)) is None


def test_station_health_counts_from_the_archive_start_of_the_kind_not_the_gauges_own_first_row():
    n = 10 * 96
    ref = readings("R", "rf", "2024-11-01", n)
    late = readings("L", "rf", "2024-11-06", n // 2)                # silent for the first 5 days of the period
    out = {h["graph_id"]: h for h in sug.station_health(pd.concat([ref, late]), date(2024, 11, 1), date(2024, 11, 10))}
    assert out["L"]["stale_pct"] == 0.5 and out["R"]["stale_pct"] == 0.0
