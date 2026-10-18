from datetime import date, datetime, timedelta

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


def add(conn, street, at, level=Level.WARNING, *, replay=False, backfill=True):
    return repo.insert_alerts(conn, [alert(street, at, level)], is_replay=replay, is_backfill=backfill)[0]


def episode(conn, street, at, level=Level.WARNING, hours=1):
    """One alert followed by its all-clear `hours` later (backfill rows)."""
    add(conn, street, at, level)
    repo.insert_alerts(conn, [alert(street, at + timedelta(hours=hours), Level.NORMAL, "all_clear")], is_replay=False, is_backfill=True)


def confirm(conn, aid, street, at, source="resident", n=2):
    for i in range(n):
        repo.insert_answer(conn, {"device_id": f"{aid[-12:]}-{i}", "alert_id": aid, "street_id": street, "answer": "yes",
                                  "answered_at": at + timedelta(minutes=10 + i), "source": source})


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
    rain = {datetime(2024, 11, 3, 6): 35.0, datetime(2024, 11, 10, 6): 42.0, datetime(2024, 11, 17, 6): 48.0}
    out = run(conn, onset_rain=lambda s, at: rain[at])
    assert rules(out) == ["SUG-1"]
    s = out[0]
    assert s["priority"] == "high" and s["street_id"] == "BBR-a" and s["street_name"] == "Jalan A"
    assert s["evidence"]["rain_at_onset_mm"] == [35.0, 42.0, 48.0]
    assert s["evidence"]["flood_dates"] == ["2024-11-03", "2024-11-10", "2024-11-17"]
    assert "drainage capacity review" in s["text"] and "Jalan A" in s["text"] and s["text"].endswith(END)
    assert s["status"] == "open" and s["note"] is None


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
    assert out[0]["priority"] == "high" and "flap gates" in out[0]["text"] and out[0]["text"].endswith(END)
    assert out[0]["evidence"]["share_near_high_tide"] == 1.0
    assert out[0]["evidence"]["flood_dates"] == ["2024-11-03", "2024-11-10", "2024-11-17"]


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
    assert len(out[0]["evidence"]["flood_dates"]) == 5 and out[0]["text"].endswith(END)
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
    assert out[0]["priority"] == "high" and out[0]["evidence"]["missed_floods"] == 2
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
    out = run(conn, health=health(87.3))
    assert rules(out) == ["SUG-7"]
    s = out[0]
    assert s["priority"] == "low" and s["street_id"] == "station:26558" and s["street_name"] == "Kg. Perepat, Kapar"
    assert s["evidence"]["stale_pct"] == 87.3 and s["text"].endswith(END)
    assert "backup station" in s["text"]


def test_sug7_threshold_is_strictly_above_ten_percent(conn):
    assert run(conn, health=health(10.0)) == []
    assert run(conn, health=health(0.0)) == []
    assert rules(run(conn, health=health(10.5))) == ["SUG-7"]


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
    ev = pd.DataFrame({"street_id": ["BBR-a"] * 3, "flooded": [1, 1, 1], "date_precision": ["hour"] * 3,
                       "start_time_local": [datetime(2024, 11, d, 13, 0) for d in (3, 10, 17)]})
    assert rules(run(conn, events=ev)) == ["SUG-2"]
    assert run(conn) == []


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
    out = {h["graph_id"]: h for h in sug.station_health(pd.concat([good, dead, short]), date(2024, 11, 1),
                                                        date(2024, 11, 10), names={"D": "Dead gauge"})}
    assert out["G"]["stale_pct"] == 0.0
    assert out["D"]["stale_pct"] == 80.0 and out["D"]["name"] == "Dead gauge"
    assert out["S"]["stale_pct"] == 50.0 and out["S"]["name"] == "S"


def test_station_health_takes_worst_series_of_a_station():
    n = 96
    rf = readings("X", "rf", "2024-11-01", n)
    wl = readings("X", "wl", "2024-11-01", n, np.full(n, np.nan))
    [h] = sug.station_health(pd.concat([rf, wl]), date(2024, 11, 1), date(2024, 11, 1))
    assert h["stale_pct"] == 100.0


def test_station_health_empty_input():
    empty = pd.DataFrame(columns=["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"])
    assert sug.station_health(empty, date(2024, 11, 1), date(2024, 11, 2)) == []
