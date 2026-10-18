import json
from datetime import datetime
from pathlib import Path

from floodready import met_parse

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return met_parse.parse_warnings(json.loads((FIX / name).read_text(encoding="utf-8")))


def test_only_land_rain_warnings_are_kept():
    ws = load("met_thunderstorm_klang_listed.json")
    assert len(ws) == 1                      # the sea warning and "No Advisory" in the payload are dropped
    w = ws[0]
    assert w["title_en"] == "Thunderstorms Warning" and w["title_ms"] == "Amaran Ribut Petir"
    assert w["valid_from"] == datetime(2026, 10, 16, 15, 0) and w["valid_to"] == datetime(2026, 10, 16, 20, 0)


def test_districts_are_read_per_state():
    w = load("met_thunderstorm_klang_listed.json")[0]
    assert {"Klang", "Petaling"} <= w["areas"]["Selangor"]
    assert w["areas"]["Melaka"] == set()     # no bracket = the whole state
    assert "Sabah" in w["areas"] and "Sarawak" in w["areas"]


def test_names_area_bare_state_and_listed_district():
    bare = load("met_thunderstorm_selangor_bare.json")[0]
    listed = load("met_thunderstorm_klang_listed.json")[0]
    other = load("met_thunderstorm_selangor_other_districts.json")[0]
    assert met_parse.names_area(bare, "Selangor", "Klang")
    assert met_parse.names_area(listed, "Selangor", "Klang")
    assert not met_parse.names_area(other, "Selangor", "Klang")      # Selangor named, but not Klang
    assert met_parse.names_area(other, "Selangor", "Hulu Langat")


def test_overlaps_the_window():
    w = load("met_thunderstorm_klang_listed.json")[0]
    assert met_parse.overlaps(w, datetime(2026, 10, 16, 16, 0), datetime(2026, 10, 17, 16, 0))
    assert not met_parse.overlaps(w, datetime(2026, 10, 16, 20, 0), datetime(2026, 10, 17, 20, 0))   # expired
    assert met_parse.overlaps(w, datetime(2026, 10, 16, 10, 0), datetime(2026, 10, 16, 18, 0))       # already running


def test_empty_or_bad_payload():
    assert met_parse.parse_warnings([]) == []
    assert met_parse.parse_warnings([{"warning_issue": None, "text_en": None}]) == []
