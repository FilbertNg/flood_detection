from datetime import datetime, timedelta

from floodready.stats.episodes import episodes

T = datetime(2024, 4, 10, 0, 0)
CD = timedelta(minutes=60)


def row(minutes, kind="alert", level="watch", street="BBR-a"):
    return {"alert_id": f"{street}-{minutes}-{kind}", "street_id": street, "kind": kind, "level": level,
            "issued_at": (T + timedelta(minutes=minutes)).isoformat()}


def test_flapping_within_cooldown_merges_and_keeps_highest_level():
    rows = [row(0), row(10, "all_clear", "normal"), row(40, level="warning"), row(50, "all_clear", "normal"),
            row(80, level="watch"), row(90, "all_clear", "normal")]
    [e] = episodes(rows, CD)
    assert e["rows"] == 3 and e["level"] == "warning" and e["start"] == T and e["end"] == T + timedelta(minutes=90)


def test_alert_after_cooldown_is_a_new_episode():
    rows = [row(0), row(10, "all_clear", "normal"), row(200), row(210, "all_clear", "normal")]
    assert len(episodes(rows, CD)) == 2


def test_escalation_while_open_stays_one_episode():
    [e] = episodes([row(0), row(20, level="warning"), row(40, level="danger"), row(90, "all_clear", "normal")], CD)
    assert e["level"] == "danger" and e["rows"] == 3


def test_open_episode_has_no_end_and_streets_are_separate():
    out = episodes([row(0), row(5, street="BBR-b")], CD)
    assert [(e["street_id"], e["end"]) for e in out] == [("BBR-a", None), ("BBR-b", None)]
    assert out[0]["alert_ids"] == ["BBR-a-0-alert"]


def test_unsorted_input_and_seventy_six_watch_rows():
    rows = []
    for k in range(76):
        rows += [row(k * 30), row(k * 30 + 5, "all_clear", "normal")]
    assert len(episodes(list(reversed(rows)), CD)) == 1


def test_open_episode_splits_after_48h_without_a_row():
    rows = [row(0), row(60, level="warning"), row(60 + 49 * 60, level="watch"), row(60 + 49 * 60 + 30, "all_clear", "normal")]
    a, b = episodes(rows, CD)
    assert a["end"] == T + timedelta(minutes=60) and a["level"] == "warning"
    assert b["start"] == T + timedelta(minutes=60 + 49 * 60) and b["end"] is not None and a["rows"] == 2
    [one] = episodes([row(0), row(47 * 60, level="warning"), row(47 * 60 + 5, "all_clear", "normal")], CD)
    assert one["level"] == "warning"
