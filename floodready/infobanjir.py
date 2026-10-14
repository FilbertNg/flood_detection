"""Parsers and helpers for JPS Public Infobanjir (publicinfobanjir.water.gov.my).

Live tables are server-rendered HTML; history comes from the JSON endpoints
behind the station graph pages. All times are local (MYT, UTC+8), naive.
See DATA_SPEC / Training Data Spec, Dataset 3.
"""
from __future__ import annotations

import calendar
import html
import json
import re
from datetime import date, datetime, timedelta

BASE_URL = "https://publicinfobanjir.water.gov.my"
WL_LIVE_URL = BASE_URL + "/aras-air/data-paras-air/aras-air-data/"
RF_LIVE_URL = BASE_URL + "/wp-content/themes/shapely/agency/searchresultrainfall.php"
WL_HIST_URL = BASE_URL + "/wp-content/themes/enlighten/query/searchresultwaterleveldtlead.php"
RF_HIST_URL = BASE_URL + "/wp-content/themes/enlighten/query/searchresultrainfalldthourlylead.php"

MISSING = -9999
_ROW_START = "<td data-th='No'>"
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG = re.compile(r"<[^>]+>")
_GRAPH_ID = re.compile(r"stationid=([^'\"&>\s]+)")
_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_EMPTY_VALUE = re.compile(r":\s*([,}])")


def wl_live_params(state: str) -> dict:
    return {"state": state, "district": "ALL", "station": "ALL", "lang": "en"}


def rf_live_params(state: str) -> dict:
    return {"state": state, "district": "ALL", "station": "ALL", "language": "1", "loginStatus": "0"}


def to_float(value) -> float | None:
    """Parse a reading; sensor faults (-9999) and blanks become None, never 0."""
    if value is None:
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return None if number == MISSING else number


def parse_dt(text: str) -> datetime | None:
    text = (text or "").strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _clean(cell_html: str) -> str:
    return html.unescape(_TAG.sub("", cell_html)).strip()


def _rows(page: str, n_cells: int) -> list[list[str]]:
    """Split a table into rows of raw cell HTML.

    Rows are found by their first cell, not by <tr>, because the rainfall
    page omits opening <tr> tags. Only the first n_cells are kept, so page
    content after the last row is ignored.
    """
    rows = []
    for chunk in page.split(_ROW_START)[1:]:
        cells = _CELL.findall(_ROW_START + chunk)[:n_cells]
        if len(cells) == n_cells:
            rows.append(cells)
    return rows


def _graph_id(cells: list[str]) -> str | None:
    for cell in cells:
        match = _GRAPH_ID.search(cell)
        if match:
            return match.group(1)
    return None


def parse_wl_live(page: str, state: str) -> list[dict]:
    """Live water-level table: No, ID, Name, District, Basin, Sub-basin,
    Last update, Level (graph link), Normal, Alert, Warning, Danger."""
    out = []
    for cells in _rows(page, 12):
        out.append({
            "state": state,
            "graph_id": _graph_id(cells),
            "station_code": _clean(cells[1]),
            "station_name": _clean(cells[2]),
            "district": _clean(cells[3]),
            "main_basin": _clean(cells[4]),
            "sub_basin": _clean(cells[5]),
            "source_time": parse_dt(_clean(cells[6])),
            "wl_m": to_float(_clean(cells[7])),
            "wl_normal_m": to_float(_clean(cells[8])),
            "wl_alert_m": to_float(_clean(cells[9])),
            "wl_warning_m": to_float(_clean(cells[10])),
            "wl_danger_m": to_float(_clean(cells[11])),
        })
    return out


def _rf_header_dates(page: str) -> list[str]:
    headers = [_clean(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", page, re.S)]
    return [datetime.strptime(h, "%d/%m/%Y").date().isoformat() for h in headers if _DATE.match(h)]


def parse_rf_live(page: str, state: str) -> list[dict]:
    """Live rainfall table: No, ID, Name, District, Last update, six daily
    totals (dates from the header), rain since midnight (graph link), 1 h."""
    dates = _rf_header_dates(page)
    out = []
    for cells in _rows(page, 13):
        daily = [to_float(_clean(c)) for c in cells[5:11]]
        out.append({
            "state": state,
            "graph_id": _graph_id(cells),
            "station_code": _clean(cells[1]),
            "station_name": _clean(cells[2]),
            "district": _clean(cells[3]),
            "source_time": parse_dt(_clean(cells[4])),
            "daily_mm": dict(zip(dates, daily)),
            "rain_since_midnight_mm": to_float(_clean(cells[11])),
            "rain_1h_mm": to_float(_clean(cells[12])),
        })
    return out


def parse_history(text: str) -> dict:
    """Parse a history endpoint response. Raises on malformed JSON so a
    broken download is never mistaken for 'no data'."""
    if "No result" in text:
        return {"info": {}, "values": []}
    # JPS sometimes writes an empty value ("cdaily":,) - read it as null.
    body = _EMPTY_VALUE.sub(r":null\1", text[text.find("{"):])
    payload = json.loads(body)
    return {"info": payload.get("info", {}), "values": payload.get("values", [])}


def _quarter_hour_values(payload: dict):
    for value in payload["values"]:
        when = parse_dt(value["dt"])
        if when is not None and when.minute % 15 == 0:
            yield when, value


def wl_history_rows(payload: dict, graph_id: str) -> list[dict]:
    info = payload["info"]
    thresholds = {
        "wl_normal_m": to_float(info.get("normal")),
        "wl_alert_m": to_float(info.get("alert")),
        "wl_warning_m": to_float(info.get("warning")),
        "wl_danger_m": to_float(info.get("danger")),
    }
    rows = []
    for when, value in _quarter_hour_values(payload):
        level = None if to_float(value.get("raw")) is None else to_float(value.get("final"))
        rows.append({"graph_id": graph_id, "time_local": when, "wl_m": level, **thresholds})
    return rows


def rf_history_rows(payload: dict, graph_id: str) -> list[dict]:
    """15-min rain per quarter hour. Rows between quarter hours repeat the
    last value, and a quarter hour with raw=-9999 is missing, not zero."""
    rows = []
    for when, value in _quarter_hour_values(payload):
        rain = None if to_float(value.get("raw")) is None else to_float(value.get("c15min"))
        rows.append({"graph_id": graph_id, "time_local": when, "rain_15min_mm": rain})
    return rows


def month_chunks(start: date, end: date) -> list[tuple[str, str]]:
    """Calendar-month request windows (the endpoints fail on ~6-month spans)."""
    chunks = []
    current = start
    while current <= end:
        last_day = calendar.monthrange(current.year, current.month)[1]
        chunk_end = min(date(current.year, current.month, last_day), end)
        chunks.append((current.strftime("%d/%m/%Y 00:00"), chunk_end.strftime("%d/%m/%Y 23:45")))
        current = chunk_end + timedelta(days=1)
    return chunks


def is_stale(source_time: datetime | None, now_local: datetime, max_age: timedelta = timedelta(hours=2)) -> bool:
    """Both times in MYT. A missing timestamp counts as stale."""
    return source_time is None or now_local - source_time > max_age
