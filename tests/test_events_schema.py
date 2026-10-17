"""Schema checks for the news-label table data/events/events.csv (WP6 L1).

Columns follow training-data-spec Dataset 1, plus three additions the spec lacks:
event_date (the spec only encodes the date inside event_id), street_ids (matched
BBR street ids, ';'-separated) and status (draft until a human fills checked_by).
"""

import csv
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "data" / "events" / "events.csv"
STREETS = ROOT / "assets" / "geo" / "bbr_streets.geojson"

COLUMNS = [
    "event_id", "event_date", "start_time_local", "report_time_local", "date_precision",
    "place_name", "street_ids", "lat", "lon", "geo_precision", "district", "sdp_township",
    "flood_type", "flooded", "depth_m", "homes_affected", "rain_reported_mm",
    "rain_station_name", "river_level_m", "river_danger_m", "river_station_name",
    "tide_mentioned", "evidence_quote", "source_url", "source_type", "source_lang",
    "checked_by", "status",
]
ENUMS = {
    "date_precision": {"hour", "day", "month", "season"},
    "geo_precision": {"street", "taman", "district"},
    "flood_type": {"flash", "river", "mixed"},
    "flooded": {"0", "1"},
    "tide_mentioned": {"0", "1"},
    "source_type": {"news", "bomba", "hotspot_list", "sdp_log", "resident_group", "app_report"},
    "source_lang": {"ms", "en"},
    "status": {"draft", "checked"},
}
REQUIRED = ["event_id", "event_date", "date_precision", "place_name", "geo_precision",
            "district", "flood_type", "flooded", "evidence_quote", "source_url",
            "source_type", "source_lang", "status", "tide_mentioned"]
FLOATS = ["lat", "lon", "depth_m", "rain_reported_mm", "river_level_m", "river_danger_m"]
SEED_IDS = {  # spec seed incidents (the multi-day Dec 2021 river flood is dated by its source)
    "BBR-2024-11-12-01", "BBR-2024-05-memorandum", "BBR-2023-06-04-01",
    "BBR-2021-12-17-01", "BBR-2017-11-07-01", "USJ-2025-04-23-01",
}


@pytest.fixture(scope="module")
def rows():
    with EVENTS.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == COLUMNS
        return list(reader)


def test_file_has_rows(rows):
    assert len(rows) >= len(SEED_IDS)


def test_event_ids_unique(rows):
    ids = [r["event_id"] for r in rows]
    assert len(ids) == len(set(ids))


def test_seed_incidents_present(rows):
    assert SEED_IDS <= {r["event_id"] for r in rows}


def test_required_fields_non_empty(rows):
    for r in rows:
        for col in REQUIRED:
            assert r[col].strip(), f"{r['event_id']}: {col} is empty"


def test_enums(rows):
    for r in rows:
        for col, allowed in ENUMS.items():
            assert r[col] in allowed, f"{r['event_id']}: {col}={r[col]!r}"


def test_evidence_quote_short_and_url_valid(rows):
    for r in rows:
        assert 0 < len(r["evidence_quote"]) <= 300, r["event_id"]
        assert re.match(r"^https?://\S+$", r["source_url"]), r["event_id"]


def test_dates_match_precision(rows):
    for r in rows:
        d = r["event_date"]
        if r["date_precision"] == "month":
            assert re.fullmatch(r"\d{4}-\d{2}", d), r["event_id"]
        else:
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d), r["event_id"]
        for col in ("start_time_local", "report_time_local"):
            if r[col]:
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", r[col]), r["event_id"]
                assert r[col].startswith(d), f"{r['event_id']}: {col} not on event_date"


def test_numeric_fields_parse(rows):
    for r in rows:
        for col in FLOATS:
            if r[col]:
                float(r[col])
        if r["homes_affected"]:
            int(r["homes_affected"])


def test_street_ids_exist_in_street_file(rows):
    known = {f["properties"]["street_id"] for f in json.loads(STREETS.read_text("utf-8"))["features"]}
    for r in rows:
        for sid in filter(None, r["street_ids"].split(";")):
            assert sid in known, f"{r['event_id']}: unknown street_id {sid}"
        if r["geo_precision"] == "street":
            assert r["street_ids"], f"{r['event_id']}: street precision needs street_ids"


def test_checked_by_only_empty_while_draft(rows):
    for r in rows:
        if r["status"] == "checked":
            assert r["checked_by"].strip(), f"{r['event_id']}: checked row needs checked_by"
        else:
            assert not r["checked_by"].strip(), f"{r['event_id']}: draft rows must leave checked_by to a human"
