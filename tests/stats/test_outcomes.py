from datetime import datetime, timedelta

import pandas as pd

from floodready.stats.outcomes import alert_outcome, missed_floods, news_outcomes

T0 = datetime(2024, 11, 12, 9, 0)


def ans(device, kind="yes", minutes=10, photo=None, dist=None, status="pending", street="BBR-a", source="resident"):
    return {"answer_id": f"{device}-{kind}-{minutes}", "device_id": device, "street_id": street, "answer": kind,
            "photo_path": photo, "distance_m": dist, "review_status": status, "source": source,
            "answered_at": (T0 + timedelta(minutes=minutes)).isoformat()}


def out(answers, sensor=False):
    return alert_outcome(answers, sensor, issued_at=T0)


def test_no_answers_is_unverified():
    assert out([]) == "unverified"


def test_two_distinct_yes_confirm():
    assert out([ans("d1"), ans("d2")]) == "confirmed"


def test_same_device_twice_is_one_yes():
    assert out([ans("d1"), ans("d1", minutes=20)]) == "unverified"


def test_one_yes_alone_is_unverified_but_with_photo_confirms():
    assert out([ans("d1")]) == "unverified"
    assert out([ans("d1", photo="x.jpg")]) == "confirmed"


def test_three_no_without_yes_is_not_confirmed():
    assert out([ans(f"d{i}", "no") for i in range(3)]) == "not_confirmed"
    assert out([ans(f"d{i}", "no") for i in range(2)]) == "unverified"


def test_a_yes_blocks_not_confirmed():
    assert out([ans(f"d{i}", "no") for i in range(3)] + [ans("y")]) == "unverified"


def test_not_sure_and_report_are_ignored():
    assert out([ans("a", "not_sure"), ans("b", "not_sure"), ans("c", "report")]) == "unverified"


def test_sensor_above_threshold_confirms():
    assert out([], sensor=True) == "confirmed"
    assert out([ans(f"d{i}", "no") for i in range(3)], sensor=True) == "confirmed"


def test_far_answers_count_half():
    assert out([ans("a", dist=1500), ans("b", dist=2000)]) == "unverified"                       # 0.5 + 0.5
    assert out([ans("a", dist=1500), ans("b", dist=2000), ans("c", dist=3000), ans("d", dist=900)]) == "confirmed"   # 1.5 + 1
    assert out([ans(f"d{i}", "no", dist=1500) for i in range(5)]) == "unverified"                # 2.5 < 3
    assert out([ans(f"d{i}", "no", dist=1500) for i in range(6)]) == "not_confirmed"             # 3.0
    assert out([ans("a", photo="x.jpg", dist=1500)]) == "unverified"                             # far photo is half a yes
    assert out([ans("a", dist=1000), ans("b", dist=999)]) == "confirmed"                         # 1 km itself is not "more than"


def test_only_the_first_three_hours_count():
    assert out([ans("a", minutes=181), ans("b", minutes=200)]) == "unverified"
    assert out([ans("a", minutes=180), ans("b", minutes=30)]) == "confirmed"
    assert out([ans("a", minutes=-5), ans("b", minutes=30)]) == "unverified"                     # before the alert


def test_spam_answers_do_not_count():
    assert out([ans("a", status="spam"), ans("b")]) == "unverified"


# ---------- missed floods ----------

def alert(street="BBR-a", minutes=-60, level="warning", kind="alert"):
    return {"alert_id": f"{street}@{minutes}", "street_id": street, "level": level, "kind": kind,
            "issued_at": (T0 + timedelta(minutes=minutes)).isoformat()}


def test_report_backed_by_two_devices_without_warning_is_a_missed_flood():
    m = missed_floods([ans("a", "report", 0), ans("b", "report", 20)], [])
    assert len(m) == 1 and m[0]["street_id"] == "BBR-a" and m[0]["devices"] == 2


def test_single_report_needs_a_photo():
    assert missed_floods([ans("a", "report", 0)], []) == []
    assert len(missed_floods([ans("a", "report", 0, photo="p.jpg")], [])) == 1


def test_warning_or_danger_in_previous_3h_means_not_missed():
    r = [ans("a", "report", 0), ans("b", "report", 5)]
    assert missed_floods(r, [alert(minutes=-170)]) == []
    assert missed_floods(r, [alert(minutes=-170, level="danger")]) == []
    assert len(missed_floods(r, [alert(minutes=-200), alert(kind="all_clear", level="normal", minutes=-190)])) == 1
    assert len(missed_floods(r, [alert(level="watch")])) == 1             # Watch is not a Warning
    assert len(missed_floods(r, [alert(kind="all_clear", level="normal")])) == 1
    assert len(missed_floods(r, [alert(street="BBR-other")])) == 1


def test_a_warning_still_active_blocks_a_missed_flood_even_if_issued_long_before():
    r = [ans("a", "report", 0), ans("b", "report", 5)]
    assert missed_floods(r, [alert(minutes=-400)]) == []                               # never cleared: still active
    assert missed_floods(r, [alert(minutes=-400), alert(kind="all_clear", level="normal", minutes=-300)]) != []
    assert len(missed_floods(r, [alert(minutes=-400), alert(level="watch", minutes=-250)])) == 1   # downgraded to watch


def test_missed_flood_ignores_spam_demo_and_non_reports():
    r = [ans("a", "report", 0, status="spam"), ans("b", "report", 5), ans("c", "report", 6, source="demo"),
         ans("d", "yes", 7)]
    assert missed_floods(r, []) == []


def test_reports_far_apart_in_time_make_separate_events():
    r = [ans("a", "report", 0), ans("b", "report", 10), ans("c", "report", 600), ans("d", "report", 610)]
    assert len(missed_floods(r, [])) == 2


# ---------- news outcomes ----------

def test_news_outcomes_confirm_matching_alerts_only():
    events = pd.DataFrame([
        {"event_id": "e1", "street_id": "BBR-a", "start_time_local": "2024-11-12 09:30", "date_precision": "hour", "flooded": 1},
        {"event_id": "e2", "street_id": "BBR-b", "start_time_local": "2024-11-12 09:30", "date_precision": "hour", "flooded": 1},
        {"event_id": "e3", "street_id": "BBR-c", "start_time_local": "2024-11-12 09:30", "date_precision": "day", "flooded": 1},
        {"event_id": "e4", "street_id": "BBR-d", "start_time_local": "2024-11-12 09:30", "date_precision": "hour", "flooded": 0},
    ])
    alerts = [alert("BBR-a", 0), alert("BBR-b", 600), alert("BBR-c", 0), alert("BBR-d", 0), alert("BBR-e", 0)]
    assert news_outcomes(events, alerts) == {alerts[0]["alert_id"]: "confirmed"}


def test_news_outcomes_empty():
    assert news_outcomes(pd.DataFrame(), [alert()]) == {}
