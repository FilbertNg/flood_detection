"""The shared events normaliser, tested against a copy of the real file from PR #43 (WP6)."""
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from floodready.stats import events

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "events_wp6_pr43.csv"
KERAMAT = "BBR-persiaran-sungai-keramat"


@pytest.fixture
def raw():
    return pd.read_csv(FIXTURE, dtype=str)


def check(raw, event_id, by="HUMAN"):
    raw = raw.copy()
    raw.loc[raw.event_id == event_id, ["checked_by", "status"]] = [by, "checked"]
    return raw


def test_real_file_with_only_drafts_produces_nothing(raw):
    assert (raw.status == "draft").all() and raw.checked_by.isna().all()
    assert events.normalise(raw).empty
    assert events.normalise(raw, street_ids={KERAMAT}, township_name="Bandar Bukit Raja").empty


def test_a_checked_row_is_split_on_semicolons_and_uses_event_date(raw):
    out = events.normalise(check(raw, "BBR-2024-11-12-01"), street_ids={KERAMAT, "BBR-persiaran-batu-belah"})
    assert set(out.street_id) == {KERAMAT, "BBR-persiaran-batu-belah"}      # the third listed street is not in the set
    assert set(out.date) == {date(2024, 11, 12)} and out.onset.isna().all()   # day precision: a date, no time
    assert set(out.event_id) == {"BBR-2024-11-12-01"}


def test_only_this_townships_rows_are_kept(raw):
    raw = check(check(check(raw, "USJ-2025-04-23-01"), "BBR-2025-04-11-01"), "BBR-2017-11-07-01")
    out = events.normalise(raw, street_ids=set(), township_name="Bandar Bukit Raja")
    # area row of the township: kept (street None); "(adjacent)" and Subang Jaya rows: dropped
    assert list(out.event_id) == ["BBR-2017-11-07-01"] and out.street_id.isna().all()
    assert set(events.normalise(raw).event_id) == {"USJ-2025-04-23-01", "BBR-2025-04-11-01", "BBR-2017-11-07-01"}


def test_month_precision_rows_have_no_day_and_are_dropped(raw):
    assert events.normalise(check(raw, "BBR-2024-05-memorandum")).empty


def test_start_time_wins_and_gives_an_onset_only_when_precise(raw):
    raw = check(check(raw, "BBR-2024-11-28-01"), "BBR-2023-06-04-01")
    raw.loc[raw.event_id == "BBR-2024-11-28-01", "start_time_local"] = "2024-11-28 15:30"
    raw.loc[raw.event_id == "BBR-2023-06-04-01", "start_time_local"] = "2023-06-04 10:00"      # but precision is day
    out = events.normalise(raw).set_index("event_id")
    assert out.loc["BBR-2024-11-28-01", "onset"] == pd.Timestamp("2024-11-28 15:30")
    assert out.loc["BBR-2024-11-28-01", "date"] == date(2024, 11, 28)
    assert pd.isna(out.loc["BBR-2023-06-04-01", "onset"]) and out.loc["BBR-2023-06-04-01", "date"] == date(2023, 6, 4)


def test_not_flooded_rows_and_missing_columns(raw):
    raw = check(raw, "BBR-2017-11-07-01")
    raw.loc[raw.event_id == "BBR-2017-11-07-01", "flooded"] = "0"
    assert events.normalise(raw).empty
    assert events.normalise(None).empty and events.normalise(pd.DataFrame({"a": [1]})).empty


def test_normalise_is_idempotent(raw):
    once = events.normalise(check(raw, "BBR-2017-11-07-01"))
    assert events.normalise(once) is once


def test_news_outcomes_uses_the_same_rules(raw):
    from floodready.stats.outcomes import news_outcomes
    ev = check(raw, "BBR-2025-04-11-01")
    ev.loc[ev.event_id == "BBR-2025-04-11-01", ["start_time_local", "street_ids"]] = ["2025-04-11 17:00", "BBR-a"]
    alert = {"alert_id": "x", "street_id": "BBR-a", "kind": "alert", "issued_at": "2025-04-11T16:00:00+08:00"}
    assert news_outcomes(ev, [alert]) == {"x": "confirmed"}
    assert news_outcomes(raw, [alert]) == {}                      # unchecked draft: nothing


def test_street_id_stays_an_object_column_with_real_none_for_area_rows(raw):
    raw = check(check(raw, "BBR-2017-11-07-01"), "BBR-2024-11-12-01")
    out = events.normalise(raw, street_ids={KERAMAT}, township_name="Bandar Bukit Raja")
    assert out.street_id.dtype == object
    assert out.street_id.isna().sum() == 1 and any(v is None for v in out.street_id)       # not NaN
    assert all(isinstance(v, str) for v in out.street_id if v is not None)
