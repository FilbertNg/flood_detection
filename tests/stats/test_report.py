from datetime import date, datetime

import pandas as pd
import pytest

from floodready.db import repo
from floodready.stats import report, statistics
from tests.stats.test_statistics import add_alert, ans, Level


@pytest.fixture
def conn():
    with repo.connect("sqlite://").begin() as c:
        yield c


EVENTS = pd.DataFrame([
    {"event_id": "BBR-2024-11-12-01", "street_id": "A", "start_time_local": "2024-11-12 09:00", "date_precision": "hour",
     "flooded": 1, "place_name": "Persiaran Sungai Keramat, Klang", "source_type": "news", "source_url": "https://example.org/x"},
    {"event_id": "BBR-2024-10-01-01", "street_id": "A", "start_time_local": "2024-10-01 09:00", "date_precision": "hour",
     "flooded": 1, "place_name": "Other month", "source_type": "news", "source_url": "https://example.org/y"},
    {"event_id": "BBR-2024-11-15-01", "street_id": "A", "start_time_local": "2024-11-15 09:00", "date_precision": "hour",
     "flooded": 0, "place_name": "Not flooded", "source_type": "news", "source_url": "https://example.org/z"}])


def test_report_lists_the_12_nov_event(conn):
    a1 = add_alert(conn, "A", Level.WARNING, datetime(2024, 11, 12, 8, 30))
    ans(conn, "d1", a1, "A", at=datetime(2024, 11, 12, 9, 0))
    ans(conn, "d2", a1, "A", at=datetime(2024, 11, 12, 9, 5))
    repo.upsert_suggestions(conn, [
        {"id": "s-in", "street_id": "A", "rule": "SUG-5", "priority": "high", "text": "Review A.",
         "period_from": date(2024, 11, 1), "period_to": date(2024, 11, 30)},
        {"id": "s-out", "street_id": "A", "rule": "SUG-5", "priority": "high", "text": "Old.",
         "period_from": date(2024, 1, 1), "period_to": date(2024, 3, 31)}])
    r = report.monthly_report(conn, "2024-11", street_names={"A": "Street A"}, events=EVENTS)
    assert r["month"] == "2024-11"
    assert [e["event_id"] for e in r["events"]] == ["BBR-2024-11-12-01"]      # news row covers the resident flood too
    assert r["events"][0] == {"event_id": "BBR-2024-11-12-01", "date": "2024-11-12", "place": "Persiaran Sungai Keramat, Klang",
                              "street_ids": ["A"], "source_type": "news", "source_url": "https://example.org/x"}
    assert r["summary"] == statistics.stats(conn, date(2024, 11, 1), date(2024, 11, 30), events=EVENTS)["kpis"]
    assert r["summary"]["alerts"] == 1 and r["summary"]["confirmed"] == 1
    assert r["top_streets"][0]["street_id"] == "A" and r["top_streets"][0]["name"] == "Street A"
    assert [s["id"] for s in r["suggestions"]] == ["s-in"]
    assert r["suggestions"][0]["text"].endswith("Screening suggestion; site survey needed.")
    assert r["data_health"] == []


def test_resident_confirmed_flood_without_news_row_is_listed(conn):
    a1 = add_alert(conn, "A", Level.WARNING, datetime(2024, 11, 12, 8, 30))
    ans(conn, "d1", a1, "A", at=datetime(2024, 11, 12, 9, 0))
    ans(conn, "d2", a1, "A", at=datetime(2024, 11, 12, 9, 5))
    r = report.monthly_report(conn, "2024-11", street_names={"A": "Street A"})
    [e] = r["events"]
    assert (e["date"], e["street_ids"], e["source_type"], e["source_url"]) == ("2024-11-12", ["A"], "app_report", None)
    assert e["place"] == "Street A"


def test_month_must_be_valid(conn):
    for bad in ("2024-13", "202411", "2024-1", "x"):
        with pytest.raises(ValueError):
            report.monthly_report(conn, bad)
